"""Trusted-client collection boundary. No network client is created here.

Only collect(), not file-supplied completion flags, proves collection for runtime.
Injected client must implement bounded authenticated get(path), graphql(query,vars)
like pullfrog_cloud_coordinator.GitHubReadClient. Collector never accepts raw events.
"""
import copy
import pullfrog_review_contract as review
from pullfrog_standalone_contract import ContractError, binding, validate_request
from pullfrog_standalone_review import normalize

THREAD_QUERY = review.THREAD_QUERY.replace(
    "author { login }", "author { login ... on User { databaseId } ... on Bot { databaseId } __typename }")


def _fail(code):
    raise ContractError(code)


def _rest(client, path, *, checks=False):
    result, ids, total = [], set(), None
    for page in range(1, review.MAX_PAGES + 1):
        payload = client.get(f"{path}?per_page=100&page={page}")
        if checks:
            if type(payload) is not dict or type(payload.get("total_count")) is not int:
                _fail("invalid_check_collection")
            count = payload["total_count"]
            if count < 0 or count > review.MAX_ITEMS or (total is not None and count != total):
                _fail("check_collection_drift")
            total = count
            nodes = payload.get("check_runs")
        else:
            nodes = payload
        if type(nodes) is not list or len(nodes) > 100:
            _fail("invalid_rest_collection")
        for node in nodes:
            if type(node) is not dict or type(node.get("id")) is not int or node["id"] < 1:
                _fail("invalid_rest_collection_identity")
            if node["id"] in ids:
                _fail("duplicate_rest_collection_identity")
            ids.add(node["id"])
        result.extend(nodes)
        if len(result) > review.MAX_ITEMS:
            _fail("rest_collection_limit")
        if len(nodes) < 100:
            if checks and len(result) != total:
                _fail("partial_check_collection")
            return result
    _fail("rest_pagination_limit")


def _threads(client, request):
    owner, name = request["repository_slug"].split("/")
    result, cursors, ids = [], set(), set()
    cursor = None
    for _ in range(review.MAX_PAGES):
        payload = client.graphql(THREAD_QUERY, dict(owner=owner, name=name,
            number=request["pr_number"], cursor=cursor))
        if type(payload) is not dict or payload.get("errors"):
            _fail("graphql_collection_error")
        try:
            connection = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
            nodes, info = connection["nodes"], connection["pageInfo"]
        except (KeyError, TypeError):
            _fail("invalid_thread_collection")
        if type(nodes) is not list or len(nodes) > 100 or type(info) is not dict:
            _fail("invalid_thread_collection")
        for node in nodes:
            if type(node) is not dict or not isinstance(node.get("id"), str) or not node["id"]:
                _fail("invalid_thread_identity")
            if node["id"] in ids:
                _fail("duplicate_thread_identity")
            ids.add(node["id"])
            root = review._thread_root(node)
            author = root.get("author")
            if (type(author) is not dict or type(author.get("databaseId")) is not int
                    or author["databaseId"] < 1 or not author.get("login")
                    or author.get("__typename") not in ("User", "Bot")):
                _fail("missing_thread_immutable_identity")
            author["type"] = author["__typename"]
        result.extend(nodes)
        if len(result) > review.MAX_ITEMS:
            _fail("thread_collection_limit")
        if type(info.get("hasNextPage")) is not bool:
            _fail("invalid_thread_pagination")
        if not info["hasNextPage"]:
            return result
        cursor = info.get("endCursor")
        if not isinstance(cursor, str) or not cursor or cursor in cursors or not nodes:
            _fail("invalid_thread_pagination")
        cursors.add(cursor)
    _fail("thread_pagination_limit")


def collect(request, client, *, current_head_sha=None, trusted_pullfrog_identity):
    """Return normalized evidence only after all bounded reads and PR recheck.

    Caller owns authenticated client and trusted identity configuration. Errors are
    sanitized ContractError; incomplete/forged review content never becomes clean.
    """
    validate_request(request)
    bound = binding(request, head_sha=current_head_sha)
    prefix = f"/repos/{request['repository_slug']}"
    pr_path = f"{prefix}/pulls/{request['pr_number']}"
    try:
        before = client.get(pr_path)
        expected = review.identity_from_pull_request(request["repository_slug"], before)
        snapshot = dict(schema=review.SNAPSHOT_SCHEMA, binding=bound,
            expected_identity=expected,
            trusted_pullfrog_identity=copy.deepcopy(trusted_pullfrog_identity))
        snapshot["reviews"] = _rest(client, pr_path + "/reviews")
        snapshot["review_comments"] = _rest(client, pr_path + "/comments")
        snapshot["check_runs"] = _rest(client,
            f"{prefix}/commits/{bound['head_sha']}/check-runs", checks=True)
        snapshot["review_threads"] = _threads(client, request)
        after = client.get(pr_path)
        if type(before) is not dict or type(after) is not dict or before.get("number") != request["pr_number"] or after.get("number") != request["pr_number"]:
            _fail("pr_response_identity_mismatch")
        snapshot["observed_identity"] = review.identity_from_pull_request(request["repository_slug"], after)
        for pr in (before, after):
            if pr.get("state") != "open" or pr.get("draft") is not False:
                _fail("pr_not_open_ready")
        snapshot["collection_complete"] = dict.fromkeys(
            ("reviews", "review_comments", "check_runs", "review_threads"), True)
        return normalize(request, snapshot, current_head_sha=current_head_sha)
    except ContractError:
        raise
    except Exception:
        raise ContractError("trusted_review_collection_failed") from None
