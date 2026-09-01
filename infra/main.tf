data "yandex_compute_image" "ubuntu" {
  family = var.image_family
}

resource "yandex_vpc_network" "kittygram_network" {
  name        = "kittygram-network"
  description = "Network for Kittygram application"
}

resource "yandex_vpc_subnet" "kittygram_subnet" {
  name           = "kittygram-subnet"
  description    = "Subnet for Kittygram application"
  zone           = var.zone
  network_id     = yandex_vpc_network.kittygram_network.id
  v4_cidr_blocks = ["192.168.10.0/24"]
}

resource "yandex_vpc_security_group" "kittygram_sg" {
  name        = "kittygram-security-group"
  description = "Security group for Kittygram application"
  network_id  = yandex_vpc_network.kittygram_network.id

  egress {
    description    = "All outbound traffic"
    protocol       = "ANY"
    from_port      = 0
    to_port        = 65535
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "SSH access"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "HTTP access to gateway"
    protocol       = "TCP"
    port           = 9000
    v4_cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "yandex_storage_bucket" "kittygram_bucket" {
  bucket = var.storage_bucket_name
  acl    = "private"
}

locals {
  cloud_init_config = templatefile("${path.module}/cloud-init.yml", {
    ssh_public_key = var.ssh_key
    ssh_username   = var.vm_ssh_login
  })
}

resource "yandex_compute_instance" "kittygram_vm" {
  name        = "kittygram-vm"
  description = "Virtual machine for Kittygram application"
  zone        = var.zone
  platform_id = var.platform_id

  resources {
    cores         = var.cores
    memory        = var.memory
    core_fraction = var.core_fraction
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = var.disk_size
      type     = var.disk_type
    }
  }

  network_interface {
    subnet_id          = yandex_vpc_subnet.kittygram_subnet.id
    nat                = var.nat
    security_group_ids = [yandex_vpc_security_group.kittygram_sg.id]
  }

  metadata = {
    user-data = local.cloud_init_config
  }

  scheduling_policy {
    preemptible = false
  }

  labels = {
    project = "kittygram"
    env     = "production"
  }
}
