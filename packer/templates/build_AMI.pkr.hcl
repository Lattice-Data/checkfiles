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

  run_tags = {
    Name        = "packer-idan-${local.timestamp}"
    CreatedBy   = "PackerIdan"
    Project     = var.name_tag
    AutoCleanup = "false"
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

  # Copy Python package files - ensure the validators directory exists
  provisioner "shell" {
    inline = [
      "echo 'Preparing Python source directories...'",
      "sudo mkdir -p /tmp/build/src",
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

  # Execute installation scripts with proper permissions
  provisioner "shell" {
    pause_before = "60s"
    scripts = "${var.installation_scripts}"
    execute_command = "chmod +x {{.Path}}; sudo -E {{.Path}}"
    max_retries = 5
  }

  post-processor "manifest" {
    output = "manifest.json"
    custom_data = {
      ami_type = "${var.ami_type}"
    }
  }
}
