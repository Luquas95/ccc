from cc_continue.models import RunStatus
from cc_continue.runner import classify_output

SUCCESS_JSON = (
    '{"duration_api_ms":1395,"stop_reason":"end_turn",'
    '"session_id":"c972e605-eb63-410b-aa20-30c2e539337c",'
    '"total_cost_usd":0.088394,'
    '"usage":{"input_tokens":2,"cache_creation_input_tokens":21253,'
    '"cache_read_input_tokens":16690,"output_tokens":4},'
    '"is_error":false,"num_turns":1,"subtype":"success",'
    '"result":"OK","duration_ms":1760}'
)


def test_classify_success():
    result = classify_output(SUCCESS_JSON, "", 0)
    assert result.status == RunStatus.SUCCESS
    assert result.result_text == "OK"
    assert result.cost_usd == 0.088394
    assert result.input_tokens == 2
    assert result.output_tokens == 4
    assert result.session_id == "c972e605-eb63-410b-aa20-30c2e539337c"


def test_classify_invalid_session_is_hard_error():
    result = classify_output(
        "",
        "No conversation found with session ID: 00000000-0000-0000-0000-000000000000",
        1,
    )
    assert result.status == RunStatus.ERROR
    assert "No conversation found" in result.error_text


def test_classify_rate_limit_from_stderr():
    result = classify_output(
        "",
        "Claude usage limit reached. Your limit will reset at 15:30.",
        1,
    )
    assert result.status == RunStatus.RATE_LIMITED


def test_classify_rate_limit_from_is_error_json():
    payload = (
        '{"is_error":true,"result":"You have hit your usage limit, resets at 09:00",'
        '"session_id":"abc"}'
    )
    result = classify_output(payload, "", 1)
    assert result.status == RunStatus.RATE_LIMITED


def test_classify_unparseable_stdout_is_error():
    result = classify_output("not json", "", 0)
    assert result.status == RunStatus.ERROR


def test_classify_generic_failure():
    result = classify_output("", "some tool crashed unexpectedly", 1)
    assert result.status == RunStatus.ERROR
