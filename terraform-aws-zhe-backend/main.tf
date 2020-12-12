provider "random" {
  version = ">= 3.0"
}

resource "random_string" "random" {
  length  = 8
  special = false
  upper   = false
}
