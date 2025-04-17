def increment_counter(event, context):
    instance_id = event['instance_id']
    iterator = event['iterator']
    index = iterator['index']
    step = iterator['step']
    count = iterator['count']
    index += step
    return {
        'instance_id': instance_id,
        'index': index,
        'step': step,
        'count': count,
        'continue': index < count,
        'instance_name_suffix': event.get('instance_name_suffix'),
        'backend_uri': event.get('backend_uri'),
        'query': event.get('query'),
        'update': event.get('update'),
        'number_of_files_pending': event.get('number_of_files_pending')
    }
