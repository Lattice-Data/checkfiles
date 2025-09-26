import os
import json
import types
import concurrent.futures

import pytest


class InlineExecutor:
    """A fake ProcessPoolExecutor that runs tasks inline and returns real Futures.
    Compatible with `with` context and `as_completed`.
    """
    def __init__(self, *args, **kwargs):
        self._futures = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, *args, **kwargs):
        fut = concurrent.futures.Future()
        try:
            res = fn(*args, **kwargs)
            fut.set_result(res)
        except Exception as e:
            fut.set_exception(e)
        self._futures.append(fut)
        return fut


@pytest.fixture(autouse=True)
def env_setup(tmp_path, monkeypatch):
    # Ensure auth and log dir are available
    monkeypatch.setenv('PORTAL_KEY', 'k')
    monkeypatch.setenv('PORTAL_SECRET_KEY', 's')
    monkeypatch.setenv('CHECKFILES_LOG_DIR', str(tmp_path))


@pytest.fixture
def backend_file():
    return {
        'uuid': 'u-1',
        'accession': 'ACC1',
        's3_uri': 's3://bkt/file1.fastq.gz',
        '@type': ['Item', 'File', 'RawSequenceFile'],
        'file_format': 'fastq'
    }


def make_success_record(checkfiles_module, s3_path):
    rec = checkfiles_module.FileValidationRecord(s3_path, None, None)
    rec.validation_success = True
    rec.update_info({'read_count': 10, 'valid': True})
    return rec


def setup_mocks_success(monkeypatch):
    import src.checkfiles as cf

    # Run tasks inline
    monkeypatch.setattr(cf, 'ProcessPoolExecutor', InlineExecutor)

    # Return a successful validation record
    monkeypatch.setattr(
        cf, 'validate_s3_file',
        lambda s3_path, file_format, debug, validator, progress_tracker, identifier, return_record, etag: make_success_record(cf, s3_path)
    )

    # Schema not needed when compare is mocked
    monkeypatch.setattr(cf, 'fetch_schema_for_type', lambda *a, **k: {'validated': {'type': 'boolean'}})

    # Build a post_json to patch
    monkeypatch.setattr(cf, 'compare_with_db', lambda *a, **k: {'post_json': {'validated': True}})

    # ETag original and current are equal
    etags = ['E1', 'E1']
    monkeypatch.setattr(cf, 'fetch_etag_for_uuid', lambda *a, **k: etags.pop(0))

    # Credentials expired -> proceed
    monkeypatch.setattr(cf, 'check_credentials_expired', lambda *a, **k: True)

    # Patch succeeds
    monkeypatch.setattr(cf, 'patch_file', lambda *a, **k: {'ok': True})

    # S3 tagging succeeds
    monkeypatch.setattr(cf, 'set_s3_tags', lambda s3_uri, *_: {'status': 'success'})

    # Do not write real log content to simplify
    monkeypatch.setattr(cf, 'write_result_to_progress_log', lambda *_: None)


def setup_mocks_etag_mismatch(monkeypatch):
    import src.checkfiles as cf
    monkeypatch.setattr(cf, 'ProcessPoolExecutor', InlineExecutor)
    monkeypatch.setattr(
        cf, 'validate_s3_file',
        lambda s3_path, file_format, debug, validator, progress_tracker, identifier, return_record, etag: make_success_record(cf, s3_path)
    )
    monkeypatch.setattr(cf, 'fetch_schema_for_type', lambda *a, **k: {'validated': {'type': 'boolean'}})
    monkeypatch.setattr(cf, 'compare_with_db', lambda *a, **k: {'post_json': {'validated': True}})
    etags = ['E1', 'E2']  # mismatch on recheck
    monkeypatch.setattr(cf, 'fetch_etag_for_uuid', lambda *a, **k: etags.pop(0))
    monkeypatch.setattr(cf, 'check_credentials_expired', lambda *a, **k: True)
    monkeypatch.setattr(cf, 'patch_file', lambda *a, **k: {'ok': True})
    monkeypatch.setattr(cf, 'set_s3_tags', lambda s3_uri, *_: {'status': 'success'})
    monkeypatch.setattr(cf, 'write_result_to_progress_log', lambda *_: None)


def setup_mocks_credentials_not_expired(monkeypatch):
    import src.checkfiles as cf
    monkeypatch.setattr(cf, 'ProcessPoolExecutor', InlineExecutor)
    monkeypatch.setattr(
        cf, 'validate_s3_file',
        lambda s3_path, file_format, debug, validator, progress_tracker, identifier, return_record, etag: make_success_record(cf, s3_path)
    )
    monkeypatch.setattr(cf, 'fetch_schema_for_type', lambda *a, **k: {'validated': {'type': 'boolean'}})
    monkeypatch.setattr(cf, 'compare_with_db', lambda *a, **k: {'post_json': {'validated': True}})
    monkeypatch.setattr(cf, 'fetch_etag_for_uuid', lambda *a, **k: 'E1')
    # Not expired -> skip
    monkeypatch.setattr(cf, 'check_credentials_expired', lambda *a, **k: False)
    monkeypatch.setattr(cf, 'patch_file', lambda *a, **k: {'ok': True})
    monkeypatch.setattr(cf, 'set_s3_tags', lambda s3_uri, *_: {'status': 'success'})
    monkeypatch.setattr(cf, 'write_result_to_progress_log', lambda *_: None)


def call_process(files, backend_file, update=True, backend_uri='https://portal.lattice-data.org'):
    import src.checkfiles as cf
    return cf.process_files_in_parallel(
        local_files=[],
        s3_files=files,
        file_format='fastq',
        thread_count=1,
        debug=False,
        validator=None,
        progress_tracker=None,
        backend_files=[backend_file],
        s3_uri_to_file_format={backend_file['s3_uri']: 'fastq'},
        update=update,
        backend_uri=backend_uri,
        s3_uri_to_file_map={backend_file['s3_uri']: backend_file},
        uuid_to_file_map={backend_file['uuid']: backend_file},
        ignore_active_credentials=False,
        update_s3_tags=True,
    )


def test_immediate_patch_success(monkeypatch, backend_file):
    setup_mocks_success(monkeypatch)
    results = call_process([backend_file['s3_uri']], backend_file)
    assert len(results) == 1
    r = results[0]
    assert r.validation_success is True
    assert getattr(r, 'patched', False) is True
    assert getattr(r, 's3_tagged', False) is True


def test_immediate_patch_etag_mismatch(monkeypatch, backend_file):
    setup_mocks_etag_mismatch(monkeypatch)
    results = call_process([backend_file['s3_uri']], backend_file)
    assert len(results) == 1
    r = results[0]
    assert r.validation_success is True
    # Mismatch should prevent patch
    assert getattr(r, 'patched', False) is False


def test_immediate_patch_credentials_not_expired(monkeypatch, backend_file):
    setup_mocks_credentials_not_expired(monkeypatch)
    results = call_process([backend_file['s3_uri']], backend_file)
    assert len(results) == 1
    r = results[0]
    assert r.validation_success is True
    # Not expired -> skip
    assert getattr(r, 'patched', False) is False


