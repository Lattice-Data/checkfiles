variable "aws_access_key" {
  type    = string
  default = ""
}

variable "aws_secret_key" {
  type    = string
  default = ""
}

variable "aws_profile_name" {
  type    = string
  default = "igvf-staging"
}

variable "aws_region" {
  type = string
}

variable "ssh_username" {
  type = string
  default = "ubuntu"
}

variable "name_tag" {
  type  = string
  default = "checkfiles_AMI"
}

variable "installation_scripts" {
  type = list(string)
}

variable "ami_type" {
  type = string
  description = "This will be written in custom_data in the manifest.json"
}

variable "source_ami_name" {
  type = string
  description = "Source AMI used to search for the source"
}

locals { timestamp = regex_replace(timestamp(), "[- TZ:]", "") }

source "amazon-ebs" "builder" {
  profile       = "${var.aws_profile_name}"
  ami_name      = "packer-ami-build ${local.timestamp}"
  instance_type = "m3.medium"
  region        = "${var.aws_region}"
  ssh_username  = "${var.ssh_username}"
  tags = {
    Name = "${var.name_tag}"
  }
  source_ami_filter {
    filters = {
      virtualization-type = "hvm"
        name = "${var.source_ami_name}"
        root-device-type = "ebs"
    }
    owners = ["099720109477"]
    most_recent = true
  }
}

# a build block invokes sources and runs provisioning steps on them. The
# documentation for build blocks can be found here:
# https://www.packer.io/docs/from-1.5/blocks/build
build {
  sources = ["source.amazon-ebs.builder"]

  # Create necessary directories
  provisioner "shell" {
    inline = [
      "sudo mkdir -p /tmp/build/src",
      "sudo mkdir -p /tmp/build/src/validators",
      "sudo chmod -R 777 /tmp/build"
    ]
  }

  # Copy Rust-related files
  provisioner "file" {
    source = "../../rust/Cargo.toml"
    destination = "/tmp/build/Cargo.toml"
  }

  provisioner "file" {
    source = "../../rust/Cargo.lock"
    destination = "/tmp/build/Cargo.lock"
  }

  # Create a proper Rust lib.rs file
  provisioner "shell" {
    inline = [
      "sudo mkdir -p /tmp/build/rust/src",
      "sudo chmod -R 777 /tmp/build/rust"
    ]
  }
  
  # Copy Rust source files
  provisioner "file" {
    source = "../../rust/src/"
    destination = "/tmp/build/rust/src/"
  }
  
  # Fix Rust library structure
  provisioner "shell" {
    inline = [
      "echo 'Creating Rust Cargo.toml with proper configuration'",
      "cat > /tmp/build/rust/Cargo.toml << 'EOL'",
      "[package]",
      "name = \"fastq_validator\"",
      "version = \"0.1.0\"",
      "edition = \"2021\"",
      "",
      "[lib]",
      "name = \"fastq_validator\"",
      "crate-type = [\"cdylib\"]",
      "",
      "[dependencies]",
      "pyo3 = { version = \"0.19.0\", features = [\"extension-module\"] }",
      "regex = \"1.9.0\"",
      "lazy_static = \"1.4.0\"",
      "EOL",
      "",
      "# Verify Rust file structure",
      "ls -la /tmp/build/rust",
      "ls -la /tmp/build/rust/src || echo 'No src dir'",
      "",
      "# Make sure lib.rs exists - rename if needed",
      "if [ -f \"/tmp/build/rust/src/lib.rs\" ]; then",
      "  echo 'lib.rs already exists'",
      "elif [ -f \"/tmp/build/rust/src/main.rs\" ]; then",
      "  echo 'Renaming main.rs to lib.rs'",
      "  mv /tmp/build/rust/src/main.rs /tmp/build/rust/src/lib.rs",
      "else",
      "  echo 'Creating minimal lib.rs'",
      "  echo 'use pyo3::prelude::*; #[pymodule] fn fastq_validator(_py: Python, m: &PyModule) -> PyResult<()> { Ok(()) }' > /tmp/build/rust/src/lib.rs",
      "fi"
    ]
  }

  provisioner "file" {
    source = "./rust-dependencies.json"
    destination = "/tmp/build/rust-dependencies.json"
  }

  # Copy from rust subdirectory to main build dir for existing scripts
  provisioner "shell" {
    inline = [
      "cp -r /tmp/build/rust/src /tmp/build/",
      "cp /tmp/build/rust/Cargo.toml /tmp/build/"
    ]
  }

  # Copy Python package files - ensure the validators directory exists
  provisioner "shell" {
    inline = [
      "echo 'Preparing Python source directories...'",
      "sudo mkdir -p /tmp/build/src/validators",
      "sudo chmod -R 777 /tmp/build/src"
    ]
  }
  
  # Copy main Python package files
  provisioner "file" {
    source = "../../src/"
    destination = "/tmp/build/src/"
  }
  
  provisioner "file" {
    source = "../../setup.py"
    destination = "/tmp/build/setup.py"
  }
  
  provisioner "file" {
    source = "../../pyproject.toml"
    destination = "/tmp/build/pyproject.toml"
  }
  
  # List directories for debugging
  provisioner "shell" {
    inline = [
      "echo 'Listing build directories content...'",
      "ls -la /tmp/build/",
      "ls -la /tmp/build/src/ || echo 'No src directory'",
      "ls -la /tmp/build/src/validators/ || echo 'No validators directory'"
    ]
  }

  provisioner "shell" {
    pause_before = "60s"
    scripts = "${var.installation_scripts}"
    max_retries = 5
  }

  post-processor "manifest" {
    output = "manifest.json"
    custom_data = {
      ami_type = "${var.ami_type}"
    }
  }
}
