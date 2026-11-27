"""Security spec for the files and images bucket policies.

These tests fail while terraform-aws-zhe-backend/buckets.tf grants
s3:ListBucket and s3:GetObject to Principal "*" for requests that arrive
through the looked-up S3 VPC endpoint. They pass once an anonymous caller
and an unrelated same-account principal, neither of which has an identity
policy allowing the action, are denied those operations on both buckets.

The evaluator follows the IAM and S3 documents cited in the comments. It is
not an AWS call. Endpoint behavior used here is the default CreateVpcEndpoint
policy, because this module only reads the endpoint and never sets one.
"""

from __future__ import annotations

import json
import re
import unittest
from dataclasses import dataclass, field
from pathlib import Path

BUCKETS_TF = Path(__file__).resolve().parents[1] / "buckets.tf"

# Concrete values standing in for Terraform interpolations. They are not
# credentials. The same endpoint id is what a request from the nodes subnet
# presents as aws:SourceVpce once the module has been applied.
FILES_BUCKET = "zenhubtest-files-abcdefgh"
IMAGES_BUCKET = "zenhubtest-images-abcdefgh"
FILES_BUCKET_ARN = f"arn:aws:s3:::{FILES_BUCKET}"
IMAGES_BUCKET_ARN = f"arn:aws:s3:::{IMAGES_BUCKET}"
VPCE_ID = "vpce-0aaa1111bbbb22222"
ACCOUNT = "123456789012"
PRIVATE_OBJECT_KEY = "uploads/private-issue-attachment.pdf"

# botocore 1.29.100 ec2/2016-11-15/service-2.json, CreateVpcEndpoint
# PolicyDocument: if the parameter is omitted, AWS attaches a default policy
# that allows full access to the service. This module never sets one.
DEFAULT_ENDPOINT_POLICY_ALLOWS_ALL = True

# Fixed condition keys that keep an Allow from counting as public.
# awsdocs/amazon-s3-userguide doc_source/access-control-block-public-access.md
# "The meaning of public" / "Bucket policies" (blob 468d98d47, lines 66-81).
NON_PUBLIC_CONDITION_KEYS = {
    "aws:principalorgid",
    "aws:sourceip",
    "aws:sourcearn",
    "aws:sourcevpc",
    "aws:sourcevpce",
    "aws:sourceowner",
    "aws:sourceaccount",
    "s3:x-amz-server-side-encryption-aws-kms-key-id",
    "aws:userid",
    "s3:dataaccesspointarn",
    "s3:dataaccesspointaccount",
}


@dataclass
class Principal:
    """None means an unsigned request. S3 treats that as anonymous.

    botocore 1.29.100 s3 service-2.json GetObject: granting READ to the
    anonymous user returns the object without an authorization header.
    """

    arn: str | None
    account: str | None
    anonymous: bool = False


@dataclass
class Request:
    action: str
    resource: str
    principal: Principal
    context: dict = field(default_factory=dict)
    identity_policy: dict | None = None


def load_bucket_policies(text: str) -> dict[str, dict]:
    """Return {'files': policy, 'images': policy} from buckets.tf."""
    pattern = re.compile(
        r"bucket\s*=\s*aws_s3_bucket\.(\w+)\.id\s*"
        r"policy\s*=\s*<<POLICY\n(.*?)\nPOLICY",
        re.S,
    )
    # No bucket policy at all is an implicit deny. A resource this parser
    # cannot read is a failure, so a rewrite that still grants access cannot
    # hide behind a different heredoc.
    resources = re.findall(r'resource\s+"aws_s3_bucket_policy"\s+"', text)
    matches = pattern.findall(text)
    if len(matches) != len(resources):
        raise AssertionError(
            f"parsed {len(matches)} bucket policy documents from {len(resources)} resources"
        )
    found = {
        "files": {"Version": "2012-10-17", "Statement": []},
        "images": {"Version": "2012-10-17", "Statement": []},
    }
    for bucket_resource, raw in matches:
        which = {"zhe_files": "files", "zhe_images": "images"}[bucket_resource]
        raw = raw.replace("${aws_s3_bucket.zhe_files.arn}", FILES_BUCKET_ARN)
        raw = raw.replace("${aws_s3_bucket.zhe_images.arn}", IMAGES_BUCKET_ARN)
        raw = raw.replace("${aws_s3_bucket.zhe_files.id}", FILES_BUCKET)
        raw = raw.replace("${aws_s3_bucket.zhe_images.id}", IMAGES_BUCKET)
        raw = raw.replace("${data.aws_vpc_endpoint.eks_s3.id}", VPCE_ID)
        if "${" in raw:
            raise AssertionError(f"unresolved interpolation in {which} bucket policy: {raw}")
        found[which] = json.loads(raw)
    return found


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _wildcard_match(pattern: str, value: str) -> bool:
    # IAM * matches any sequence of characters, including '/'.
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, value) is not None


def _aws_principals(principal_element) -> list[tuple[str, str]]:
    if principal_element is None:
        return []
    if principal_element == "*":
        return [("*", "*")]
    if isinstance(principal_element, str):
        return [("AWS", principal_element)]
    if not isinstance(principal_element, dict):
        raise AssertionError(f"unsupported Principal element {principal_element!r}")
    values = []
    for key in ("AWS", "Service", "CanonicalUser", "Federated"):
        if key in principal_element:
            values.extend((key, item) for item in _as_list(principal_element[key]))
    return values


def principal_matches(principal_element, principal: Principal) -> bool:
    """Resource-policy Principal match.

    "*" and {"AWS": "*"} match every caller, including anonymous
    (iam-user-guide reference_policies_elements_principal.md, blob
    cdab2ce57, lines 244-252). A specific ARN matches only that principal.
    """
    if principal_element is None:
        return False
    specs = _aws_principals(principal_element)
    for kind, value in specs:
        if kind == "*" or value == "*":
            return True
        if principal.anonymous:
            continue
        if kind == "AWS" and value == principal.arn:
            return True
        if kind == "AWS" and value == principal.account:
            return True
        root = f"arn:aws:iam::{principal.account}:root"
        if kind == "AWS" and value == root:
            return True
    return False


def _action_patterns(statement) -> tuple[list[str], bool]:
    if "NotAction" in statement and "Action" in statement:
        raise AssertionError("statement has both Action and NotAction")
    if "NotAction" in statement:
        return _as_list(statement["NotAction"]), True
    return _as_list(statement.get("Action", [])), False


def action_matches(statement, action: str) -> bool:
    patterns, negated = _action_patterns(statement)
    matched = any(
        _wildcard_match(pattern.lower(), action.lower()) for pattern in patterns
    )
    return not matched if negated else matched


def _resource_patterns(statement) -> tuple[list[str], bool]:
    if "NotResource" in statement and "Resource" in statement:
        raise AssertionError("statement has both Resource and NotResource")
    if "NotResource" in statement:
        return _as_list(statement["NotResource"]), True
    return _as_list(statement.get("Resource", [])), False


def resource_matches(statement, resource: str) -> bool:
    patterns, negated = _resource_patterns(statement)
    matched = any(_wildcard_match(pattern, resource) for pattern in patterns)
    return not matched if negated else matched


def _condition_values_match(operator: str, policy_values, request_value: str | None) -> bool:
    values = [str(item) for item in _as_list(policy_values)]
    # reference_policies_multi-value-conditions.md (blob 8d1882ab) line 17:
    # multiple values for one positive operator are a logical OR.
    # A missing request key makes StringEquals false and StringNotEquals
    # true (reference_policies_elements_condition_operators.md line 10).
    base = operator.split(":", 1)[-1]
    if base == "StringEquals":
        return request_value is not None and request_value in values
    if base == "StringEqualsIgnoreCase":
        return request_value is not None and request_value.lower() in {
            item.lower() for item in values
        }
    if base == "StringLike":
        return request_value is not None and any(
            _wildcard_match(item, request_value) for item in values
        )
    if base == "StringNotEquals":
        return request_value is None or request_value not in values
    if base == "StringNotLike":
        return request_value is None or all(
            not _wildcard_match(item, request_value) for item in values
        )
    raise AssertionError(f"condition operator {operator} is not implemented")


def condition_matches(condition, context: dict) -> bool:
    if not condition:
        return True
    # Multiple operators and keys are a logical AND (multi-value doc line 17).
    for operator, keys in condition.items():
        for key, policy_values in keys.items():
            request_value = None
            for present, value in context.items():
                if present.lower() == key.lower():
                    request_value = value
                    break
            if not _condition_values_match(operator, policy_values, request_value):
                return False
    return True


def statement_matches(statement, request: Request) -> bool:
    element = statement.get("Principal")
    if "NotPrincipal" in statement:
        if element is not None:
            raise AssertionError("statement has both Principal and NotPrincipal")
        if principal_matches(statement["NotPrincipal"], request.principal):
            return False
    elif not principal_matches(element, request.principal):
        return False
    if not action_matches(statement, request.action):
        return False
    if not resource_matches(statement, request.resource):
        return False
    if not condition_matches(statement.get("Condition"), request.context):
        return False
    return True


def _is_fixed_token(value: str) -> bool:
    return "*" not in value and "${" not in value and value != ""


def _statement_is_non_public(statement) -> bool:
    """An Allow is non-public only when every grantee is a fixed principal or a listed key."""
    if statement.get("Effect") != "Allow":
        return True
    element = statement.get("Principal")
    specs = _aws_principals(element)
    principal_is_fixed = bool(specs) and all(
        kind == "AWS" and value != "*" and _is_fixed_token(value) for kind, value in specs
    )
    condition_is_fixed = False
    for _operator, keys in (statement.get("Condition") or {}).items():
        for key, policy_values in keys.items():
            if key.lower() not in NON_PUBLIC_CONDITION_KEYS:
                continue
            values = [str(item) for item in _as_list(policy_values)]
            if values and all(_is_fixed_token(item) for item in values):
                condition_is_fixed = True
    if principal_is_fixed or condition_is_fixed:
        # A wildcard principal still needs the fixed condition. A fixed
        # principal does not. One public statement makes the policy public
        # (block-public-access.md lines 139-141); that is applied by the caller.
        if any(value == "*" or kind == "*" for kind, value in specs):
            return condition_is_fixed
        return True
    return False


def policy_is_public(policy: dict) -> bool:
    # S3 starts from the assumption that the policy is public, then checks
    # each grant (block-public-access.md lines 66-67 and 139-141).
    return any(
        statement.get("Effect") == "Allow" and not _statement_is_non_public(statement)
        for statement in policy.get("Statement", [])
    )


def bucket_request_allowed(bucket_policy: dict, request: Request) -> bool:
    """Same-account and anonymous decision for one bucket policy.

    Default is implicit deny. An applicable Allow in the bucket policy
    authorizes an anonymous caller and a same-account caller even when the
    identity policy has no Allow (evaluation-logic.md lines 63-66 and
    133-134; principal.md line 242). An applicable Deny wins (line 209).

    RestrictPublicBuckets does not apply when the policy is non-public.
    A Principal "*" Allow conditioned on a fixed aws:SourceVpce value is
    non-public (block-public-access.md lines 73 and 117-125).
    """
    if not DEFAULT_ENDPOINT_POLICY_ALLOWS_ALL:
        return False

    for statement in bucket_policy.get("Statement", []):
        if statement.get("Effect") == "Deny" and statement_matches(statement, request):
            return False
    if request.identity_policy:
        for statement in request.identity_policy.get("Statement", []):
            if statement.get("Effect") == "Deny" and statement_matches(statement, request):
                return False

    if policy_is_public(bucket_policy) and request.principal.anonymous:
        # RestrictPublicBuckets blocks anonymous access derived from a public policy.
        return False

    if request.principal.anonymous or _resource_allow_is_direct(bucket_policy, request):
        for statement in bucket_policy.get("Statement", []):
            if statement.get("Effect") == "Allow" and statement_matches(statement, request):
                return True
        if request.principal.anonymous:
            return False

    if request.identity_policy:
        for statement in request.identity_policy.get("Statement", []):
            if statement.get("Effect") == "Allow" and statement_matches(statement, request):
                return True
    return False


def _resource_allow_is_direct(bucket_policy: dict, request: Request) -> bool:
    """Principal "*" needs no identity Allow. An account-root grant does.

    principal.md lines 56-68: an account id delegates to that account, and
    an administrator still grants the identity. principal.md line 242: a
    wildcard Allow does not require another permission for principals in
    the account. Anonymous callers have no identity policy at all.
    """
    for statement in bucket_policy.get("Statement", []):
        if statement.get("Effect") != "Allow" or not statement_matches(statement, request):
            continue
        specs = _aws_principals(statement.get("Principal"))
        if any(kind == "*" or value == "*" for kind, value in specs):
            return True
        if any(kind == "AWS" and value == request.principal.arn for kind, value in specs):
            return True
    return False


def anonymous() -> Principal:
    return Principal(arn=None, account=None, anonymous=True)


def unrelated_role() -> Principal:
    return Principal(
        arn=f"arn:aws:iam::{ACCOUNT}:role/other-namespace-workload",
        account=ACCOUNT,
        anonymous=False,
    )


def vpce_context(principal: Principal, vpce: str | None = VPCE_ID) -> dict:
    context = {}
    if vpce is not None:
        # Present only when the caller uses a VPC endpoint
        # (reference_policies_condition-keys.md lines 1110-1112).
        context["aws:SourceVpce"] = vpce
    if not principal.anonymous:
        context["aws:PrincipalArn"] = principal.arn
        context["aws:PrincipalAccount"] = principal.account
    return context


class EvaluatorLocksToPublishedExamples(unittest.TestCase):
    """The harness must accept the published examples before it judges this repo."""

    def test_wildcard_without_condition_is_public_and_block_public_access_denies_anonymous(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Principal": "*",
                    "Effect": "Allow",
                    "Action": "s3:PutObject",
                    "Resource": "*",
                }
            ],
        }
        self.assertTrue(policy_is_public(policy))
        request = Request(
            action="s3:PutObject",
            resource="arn:aws:s3:::example/object",
            principal=anonymous(),
            context={},
        )
        self.assertFalse(bucket_request_allowed(policy, request))

    def test_fixed_source_vpce_keeps_wildcard_allow_non_public(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Principal": "*",
                    "Effect": "Allow",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::example/*",
                    "Condition": {"StringEquals": {"aws:SourceVpce": VPCE_ID}},
                }
            ],
        }
        self.assertFalse(policy_is_public(policy))
        request = Request(
            action="s3:GetObject",
            resource="arn:aws:s3:::example/object",
            principal=anonymous(),
            context={"aws:SourceVpce": VPCE_ID},
        )
        self.assertTrue(bucket_request_allowed(policy, request))

    def test_specific_principal_denies_anonymous_and_unrelated_role(self):
        user = f"arn:aws:iam::{ACCOUNT}:user/zenhubtest-buckets"
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Principal": {"AWS": user},
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": FILES_BUCKET_ARN,
                    "Condition": {"StringEquals": {"aws:SourceVpce": VPCE_ID}},
                }
            ],
        }
        self.assertFalse(policy_is_public(policy))
        for principal in (anonymous(), unrelated_role()):
            request = Request(
                action="s3:ListBucket",
                resource=FILES_BUCKET_ARN,
                principal=principal,
                context=vpce_context(principal),
            )
            self.assertFalse(bucket_request_allowed(policy, request))


class VpceBucketPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUCKETS_TF.read_text()
        cls.policies = load_bucket_policies(cls.source)

    def test_module_looks_up_endpoint_and_does_not_set_an_endpoint_policy(self):
        self.assertIn('data "aws_vpc_endpoint" "eks_s3"', self.source)
        self.assertNotIn('resource "aws_vpc_endpoint"', self.source)

    def test_both_buckets_use_sse_s3_so_get_object_needs_no_kms_decrypt(self):
        # buckets.tf sets sse_algorithm = "AES256" and leaves the KMS key commented
        # out. SSE-S3 does not add a kms:Decrypt requirement to GetObject.
        algorithms = re.findall(r'sse_algorithm\s*=\s*"([^"]+)"', self.source)
        self.assertEqual(algorithms, ["AES256", "AES256"])

    def _request(self, principal, action, resource, vpce=VPCE_ID):
        return Request(
            action=action,
            resource=resource,
            principal=principal,
            context=vpce_context(principal, vpce),
            identity_policy=None,
        )

    def test_anonymous_list_objects_v2_from_vpc_endpoint_denied_on_files_and_images(self):
        # ListObjectsV2 requires s3:ListBucket (botocore 1.29.100 s3
        # service-2.json, operation ListObjectsV2).
        for which, resource in (
            ("files", FILES_BUCKET_ARN),
            ("images", IMAGES_BUCKET_ARN),
        ):
            request = self._request(anonymous(), "s3:ListBucket", resource)
            self.assertFalse(
                bucket_request_allowed(self.policies[which], request),
                f"anonymous ListObjectsV2 on the {which} bucket was allowed",
            )

    def test_anonymous_get_object_from_vpc_endpoint_denied_on_files_and_images(self):
        for which, bucket_arn in (
            ("files", FILES_BUCKET_ARN),
            ("images", IMAGES_BUCKET_ARN),
        ):
            request = self._request(
                anonymous(), "s3:GetObject", f"{bucket_arn}/{PRIVATE_OBJECT_KEY}"
            )
            self.assertFalse(
                bucket_request_allowed(self.policies[which], request),
                f"anonymous GetObject on the {which} bucket was allowed",
            )

    def test_unrelated_role_without_identity_allow_denied_list_and_get_on_both_buckets(self):
        # Same-account role with no identity-based Allow. A wildcard bucket
        # Allow still authorizes it (principal.md line 242).
        role = unrelated_role()
        cases = (
            ("files", "s3:ListBucket", FILES_BUCKET_ARN),
            ("images", "s3:ListBucket", IMAGES_BUCKET_ARN),
            ("files", "s3:GetObject", f"{FILES_BUCKET_ARN}/{PRIVATE_OBJECT_KEY}"),
            ("images", "s3:GetObject", f"{IMAGES_BUCKET_ARN}/{PRIVATE_OBJECT_KEY}"),
        )
        for which, action, resource in cases:
            request = self._request(role, action, resource)
            self.assertFalse(
                bucket_request_allowed(self.policies[which], request),
                f"{action} on the {which} bucket was allowed for an unrelated role",
            )

    def test_anonymous_requests_outside_the_endpoint_stay_denied(self):
        request = self._request(
            anonymous(),
            "s3:GetObject",
            f"{FILES_BUCKET_ARN}/{PRIVATE_OBJECT_KEY}",
            vpce=None,
        )
        self.assertFalse(bucket_request_allowed(self.policies["files"], request))
        other_endpoint = self._request(
            anonymous(),
            "s3:ListBucket",
            IMAGES_BUCKET_ARN,
            vpce="vpce-fffffffffffffffff",
        )
        self.assertFalse(bucket_request_allowed(self.policies["images"], other_endpoint))


if __name__ == "__main__":
    unittest.main()
