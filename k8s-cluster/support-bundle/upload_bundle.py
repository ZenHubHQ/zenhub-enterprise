import base64
import json
from argparse import ArgumentParser
from os import getenv, path
from sys import exit

from boto3 import client
from yaml import safe_load

access_key_id: str = getenv("SUPPORT_BUNDLE_ACCESS_KEY")
secret_access_key: str = getenv("SUPPORT_BUNDLE_SECRET_KEY")

# Optional overwrites for development/testing
bucket_name: str = getenv(
    "SUPPORT_BUNDLE_BUCKET_NAME", "zenhub-enterprise-support-bundles"
)
config_path: str = getenv(
    "SUPPORT_BUNDLE_CONFIG_FILE", "/opt/zenhub/configuration/configuration.yaml"
)
bucket_region: str = getenv("SUPPORT_BUNDLE_BUCKET_REGION", "us-west-2")


def validate_env_vars() -> None:
    if access_key_id is None or secret_access_key is None:
        print(
            "Please set SUPPORT_BUNDLE_ACCESS_KEY and SUPPORT_BUNDLE_SECRET_KEY env vars before running this script."
        )
        exit(1)


def validate_bundle_file_path(file_path: str) -> None:
    if not path.exists(file_path):
        print(
            f"File {file_path} does not exist. Please provide a valid file path to the support bundle tar file."
        )
        exit(1)


def setup_arg_parser() -> ArgumentParser:
    parser: ArgumentParser = ArgumentParser(
        description="Upload a Zenhub Enterprise support bundle to S3 storage."
    )

    parser.add_argument(
        "customer_identifier",
        type=str,
        help="An identifier to distinguish your support bundle from others. This could be your company name, or a unique identifier for your Zenhub Enterprise instance.",
    )

    parser.add_argument(
        "bundle_file_path",
        type=str,
        help="The full path to the support bundle .tar file that you want to upload.",
    )

    return parser


def get_company_name(customer_identifier: str) -> str:
    """This will attempt to find the company_name in the ZHE license token
    If it can't be found, we fall back to customer_identifier (github hostname on vm)
    In a ZHE for K8s context, this will always return the customer_identifier"""

    try:
        with open(config_path, "r") as yamlfile:
            configuration = safe_load(yamlfile)

        license_jwt_token = configuration["zenhub_configuration"][
            "ENTERPRISE_LICENSE_TOKEN"
        ]
        payload = license_jwt_token.split(".")[1]
        decoded_payload = json.loads(base64.b64decode(payload + "=="))
        company_name = decoded_payload["company_name"]

        print(f"Using '{company_name}' instead of customer_identifier.")

        return company_name
    except Exception as e:
        print(
            "Could not find company_name in license token, continuing with customer_identifier."
        )
        return customer_identifier


def upload_file_to_s3(directory_name: str, bundle_path: str) -> None:
    # The file name is the last part of the path
    bundle_file_name: str = bundle_path.split("/")[-1]
    s3_object_name: str = f"{directory_name}/{bundle_file_name}"

    s3 = client(
        "s3",
        region_name=bucket_region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    try:
        s3.upload_file(bundle_path, bucket_name, s3_object_name)
        print(
            f"Successfully uploaded bundle {s3_object_name}, please notify Zenhub Support and provide a description of the issue you are experiencing."
        )
    except Exception as e:
        print(f"Failed to upload metrics to S3.\nError: {e}")
        exit(1)


def main() -> None:
    args = setup_arg_parser().parse_args()
    if args.customer_identifier is None or args.bundle_file_path is None:
        print(
            "Usage: python upload_bundle.py <customer_identifier> <support_bundle_file_path>"
        )
        exit(1)

    validate_env_vars()
    validate_bundle_file_path(args.bundle_file_path)

    directory_name = get_company_name(args.customer_identifier)
    upload_file_to_s3(directory_name, args.bundle_file_path)


if __name__ == "__main__":
    main()
