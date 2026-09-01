output "vm_external_ip" {
  value       = yandex_compute_instance.kittygram_vm.network_interface[0].nat_ip_address
  description = "Public IPv4 address of the VM"
}

output "vm_ssh_login" {
  value       = var.vm_ssh_login
  description = "SSH user — same as REMOTE_USER secret in deploy.yml"
}

output "storage_bucket_name" {
  value       = yandex_storage_bucket.kittygram_bucket.bucket
  description = "Object Storage bucket name"
}
