data "aws_availability_zones" "available" {}

data "aws_vpc" "zhe" {
  id = var.vpc_id
}

resource "aws_subnet" "zhe_db" {
  count                = var.db_subnet_count
  vpc_id               = var.vpc_id
  cidr_block           = cidrsubnet(data.aws_vpc.zhe.cidr_block, 8, count.index + var.cidr_netnum)
  availability_zone_id = data.aws_availability_zones.available.zone_ids[count.index]

  tags = {
    Name        = "zenhub${var.env}-backend ${count.index}"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_route_table" "zhe_private_dbs" {
  vpc_id = var.vpc_id

  tags = {
    Name        = "zenhub${var.env}-backend"
    Creator     = var.creator
    Environment = var.env
    App         = "ZenHub Enterprise"
  }
}

resource "aws_route_table_association" "zhe_dbs" {
  count          = length(aws_subnet.zhe_db[*].id)
  subnet_id      = aws_subnet.zhe_db[count.index].id
  route_table_id = aws_route_table.zhe_private_dbs.id
}
