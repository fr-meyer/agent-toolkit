import copy
import importlib
import unittest
import test_pullfrog_standalone_review as review_tests


class Client:
    def __init__(self, request, snapshot):
        self.snapshot = snapshot
        self.trace = []
        self.pr = dict(number=request["pr_number"], state="open", draft=False,
            user=dict(id=26621962, login="fr-meyer", type="User"),
            base=dict(ref=request["base_ref"], sha=request["base_sha"],
                      repo=dict(full_name=request["repository_slug"])),
            head=dict(ref=request["head_ref"], sha=request["head_sha"],
                      repo=dict(full_name=request["repository_slug"])))
        self.mutate = lambda path, value: value
        self.graph_mutate = lambda value: value

    def get(self, path):
        self.trace.append(path)
        if "?" not in path:
            value = self.pr
        elif "/reviews?" in path:
            value = self.snapshot["reviews"]
        elif "/comments?" in path:
            value = self.snapshot["review_comments"]
        else:
            value = dict(total_count=len(self.snapshot["check_runs"]), check_runs=self.snapshot["check_runs"])
        return self.mutate(path, copy.deepcopy(value))

    def graphql(self, query, variables):
        self.trace.append((query, variables))
        nodes = copy.deepcopy(self.snapshot["review_threads"])
        for node in nodes:
            node["comments"]["nodes"][0]["author"]["__typename"] = "Bot"
        value = dict(data=dict(repository=dict(pullRequest=dict(reviewThreads=dict(
            nodes=nodes, pageInfo=dict(hasNextPage=False, endCursor=None))))))
        return self.graph_mutate(value)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        review_tests.ReviewTests.setUpClass()
        self.r, self.s = review_tests.ReviewTests().fixture()
        self.module = importlib.import_module("pullfrog_standalone_collector")
        self.client = Client(self.r, self.s)

    def collect(self):
        return self.module.collect(self.r, self.client,
            trusted_pullfrog_identity=self.s["trusted_pullfrog_identity"])

    def test_authenticated_read_trace(self):
        self.assertEqual(self.collect()["status"], "clean")
        trace = self.client.trace
        self.assertEqual(len(trace), 6)
        self.assertEqual(trace[0], trace[-1])
        self.assertIn("/reviews?per_page=100&page=1", trace[1])
        self.assertIn("/comments?per_page=100&page=1", trace[2])
        self.assertIn("/check-runs?per_page=100&page=1", trace[3])
        self.assertIn("... on Bot { databaseId }", trace[4][0])
        self.assertEqual(trace[4][1], dict(owner="fr-meyer", name="agent-toolkit", number=95, cursor=None))

    def test_missing_pages_errors_and_identity(self):
        for mode in ("partial", "error", "wrong_pr", "spoof", "missing_root", "graphql_error"):
            with self.subTest(mode=mode):
                self.client = Client(self.r, self.s)
                def mutate(path, value):
                    if mode == "error":
                        raise RuntimeError("private diagnostic")
                    if mode == "wrong_pr" and "?" not in path:
                        value["number"] = 96
                    if mode == "partial" and "check-runs?" in path:
                        value["total_count"] = 3
                    if mode == "spoof" and "/reviews?" in path:
                        value[0]["user"]["id"] = 999
                    return value
                self.client.mutate = mutate
                def graph(value):
                    if mode == "graphql_error":
                        value["errors"] = [dict(message="secret")]
                    if mode == "missing_root":
                        value["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"][0]["comments"]["nodes"] = []
                    return value
                self.client.graph_mutate = graph
                if mode == "spoof":
                    self.assertEqual(self.collect()["status"], "incomplete")
                else:
                    with self.assertRaises(self.module.ContractError) as ctx:
                        self.collect()
                    self.assertNotIn("private", str(ctx.exception))

    def test_rest_full_pagination(self):
        for checks in (False, True):
            trace = []
            class Pages:
                def get(inner, path):
                    trace.append(path)
                    nodes = [dict(id=i) for i in (range(1,101) if "&page=1" in path else range(101,103))]
                    return dict(total_count=102, check_runs=nodes) if checks else nodes
            result = self.module._rest(Pages(), "/repos/fr-meyer/agent-toolkit/items", checks=checks)
            self.assertEqual(len(result), 102)
            self.assertEqual(len(trace), 2)
            self.assertTrue(trace[-1].endswith("page=2"))

    def test_graphql_pagination_and_repeated_cursor(self):
        count = 0
        def graph(value):
            nonlocal count
            count += 1
            conn = value["data"]["repository"]["pullRequest"]["reviewThreads"]
            conn["nodes"][0]["id"] += str(count)
            conn["pageInfo"] = dict(hasNextPage=count == 1, endCursor="next")
            return value
        self.client.graph_mutate = graph
        self.assertEqual(self.collect()["status"], "clean")
        calls = [v for v in self.client.trace if isinstance(v, tuple)]
        self.assertEqual(calls[1][1]["cursor"], "next")
        count = 0
        def repeat(value):
            value = graph(value)
            value["data"]["repository"]["pullRequest"]["reviewThreads"]["pageInfo"]["hasNextPage"] = True
            return value
        self.client.graph_mutate = repeat
        with self.assertRaises(self.module.ContractError):
            self.collect()


if __name__ == "__main__":
    unittest.main()
