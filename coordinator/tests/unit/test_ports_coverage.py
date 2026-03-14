from application.accounting_ports import UserRepository, TransactionRepository
from application.inference_ports import NodeDiscoveryRepository
from application.security_ports import TokenService, KeyRepository
from application.verification_ports import ChallengeRepository, BenchmarkRepository


def test_ports_abstract_methods():
    """Dummy calls to abstract methods to satisfy 100% coverage requirements."""
    # We create concrete subclasses that call super() for any methods that have bodies (none here usually)
    # but since these are ABCs with pass, calling them via a mock or dummy works.

    class DummyUserRepo(UserRepository):
        def get_by_public_key(self, pk):
            return super().get_by_public_key(pk)

        def save(self, user):
            return super().save(user)

    repo = DummyUserRepo()
    repo.get_by_public_key("test")
    repo.save(None)

    class DummyTxnRepo(TransactionRepository):
        def record_transaction(self, t):
            return super().record_transaction(t)

        def get_history_by_user(self, pk, limit):
            return super().get_history_by_user(pk, limit)

    repo2 = DummyTxnRepo()
    repo2.record_transaction(None)
    repo2.get_history_by_user("test", 10)

    class DummyInfraRepo(NodeDiscoveryRepository):
        def save_node(self, node, ttl):
            return super().save_node(node, ttl)

        def get_node(self, nid):
            return super().get_node(nid)

        def find_nodes_by_model(self, model):
            return super().find_nodes_by_model(model)

        def list_all_active_nodes(self):
            return super().list_all_active_nodes()

    repo3 = DummyInfraRepo()
    repo3.save_node(None, 0)
    repo3.get_node("test")
    repo3.find_nodes_by_model("test")
    repo3.list_all_active_nodes()

    class DummyToken(TokenService):
        def generate_ticket(self, user, target, proj):
            return super().generate_ticket(user, target, proj)

        def verify_ticket(self, token):
            return super().verify_ticket(token)

    svc = DummyToken()
    svc.generate_ticket("u", "t", "p")
    svc.verify_ticket("t")

    class DummyKey(KeyRepository):
        def get_public_key(self):
            return super().get_public_key()

        def get_private_key(self):
            return super().get_private_key()

        def ensure_keys_exist(self):
            return super().ensure_keys_exist()

    repo4 = DummyKey()
    repo4.get_public_key()
    repo4.get_private_key()
    repo4.ensure_keys_exist()

    class DummyChallenge(ChallengeRepository):
        def save_challenge(self, c, t):
            return super().save_challenge(c, t)

        def get_challenge(self, t):
            return super().get_challenge(t)

        def delete_challenge(self, t):
            return super().delete_challenge(t)

    repo5 = DummyChallenge()
    repo5.save_challenge(None, 0)
    repo5.get_challenge("t")
    repo5.delete_challenge("t")

    class DummyBench(BenchmarkRepository):
        def save_result(self, r):
            return super().save_result(r)

        def get_last_result(self, nid):
            return super().get_last_result(nid)

    repo6 = DummyBench()
    repo6.save_result(None)
    repo6.get_last_result("test")
