"""Unit tests for Drain template extraction."""
from backend.detection.preprocessing.parser import (
    SERVICE_LOG_MASKS,
    create_template_miner,
    templates_of,
)


def test_variable_values_are_masked_into_one_template():
    miner = create_template_miner()
    a = miner.add_log_message("PacketResponder 1 for block blk_38865049064139660 terminating")
    b = miner.add_log_message("PacketResponder 2 for block blk_-6952295868487656571 terminating")
    assert a["cluster_id"] == b["cluster_id"]
    assert templates_of(miner)[0].template == "PacketResponder <NUM> for block <BLK> terminating"


def test_different_structures_get_different_templates():
    miner = create_template_miner()
    a = miner.add_log_message("PacketResponder 1 for block blk_1 terminating")
    b = miner.add_log_message("Receiving block blk_2 src: /10.0.0.1:50010 dest: /10.0.0.2:50010")
    assert a["cluster_id"] != b["cluster_id"]


def test_ip_addresses_are_masked():
    miner = create_template_miner()
    miner.add_log_message("Receiving block blk_2 src: /10.250.19.102:54106 dest: /10.250.19.102:50010")
    assert "<IP>" in templates_of(miner)[0].template


def test_file_paths_are_masked():
    miner = create_template_miner()
    a = miner.add_log_message("BLOCK* NameSystem.allocateBlock: /user/root/rand/_temporary/part-00001. blk_1")
    b = miner.add_log_message("BLOCK* NameSystem.allocateBlock: /user/root/sort/_temporary/part-00777. blk_2")
    assert a["cluster_id"] == b["cluster_id"]
    assert templates_of(miner)[0].template == "BLOCK* NameSystem.allocateBlock: <PATH> <BLK>"


def test_strict_threshold_keeps_different_words_apart():
    miner = create_template_miner(sim_threshold=0.9)
    a = miner.add_log_message("PacketResponder 1 for block blk_1 terminating")
    b = miner.add_log_message("PacketResponder 0 for block blk_2 Interrupted.")
    assert a["cluster_id"] != b["cluster_id"]


def test_generator_messages_share_a_template():
    miner = create_template_miner()
    a = miner.add_log_message("Payment failed for order 568987: card processor timeout after 174 ms")
    b = miner.add_log_message("Payment failed for order 114106: card processor timeout after 65 ms")
    assert a["cluster_id"] == b["cluster_id"]
    assert templates_of(miner)[0].template == (
        "Payment failed for order <NUM>: card processor timeout after <NUM> ms"
    )


def test_template_counts_are_tracked():
    miner = create_template_miner()
    for i in range(5):
        miner.add_log_message(f"Deleting block blk_{i} file /mnt/hadoop/dfs/data/current/subdir{i}/blk_{i}")
    assert sum(t.count for t in templates_of(miner)) == 5


def test_service_masks_merge_user_ids():
    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    a = miner.add_log_message("Token validated for user u6601")
    b = miner.add_log_message("Token validated for user u1234")
    assert a["cluster_id"] == b["cluster_id"]
    assert templates_of(miner)[0].template == "Token validated for user <ID>"


def test_service_masks_merge_transaction_ids():
    miner = create_template_miner(masks=SERVICE_LOG_MASKS)
    a = miner.add_log_message("Payment txn_c9731bc4b8 processed for order 845970: amount 4163.57 INR")
    b = miner.add_log_message("Payment txn_00a1f2e3d4 processed for order 123456: amount 99.10 INR")
    assert a["cluster_id"] == b["cluster_id"]
    assert templates_of(miner)[0].template == "Payment <ID> processed for order <NUM>: amount <NUM> INR"


def test_default_masks_are_unchanged_for_offline_reproducibility():
    miner = create_template_miner()
    miner.add_log_message("Token validated for user u6601")
    assert templates_of(miner)[0].template == "Token validated for user u6601"