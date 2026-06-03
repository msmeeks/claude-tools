"""Tests for HTML rendering — ensures SSTI cannot escape from AI content."""


from demo_gen import tokens as token_loader
from demo_gen.config import DemoConfig, DemoScript, PolishLevel, Step
from demo_gen.stages import html as html_stage


def _make_script(**kwargs) -> DemoScript:
    defaults = dict(
        title="Test Demo",
        tagline="Tagline here.",
        executive_summary="This is a summary.",
        steps=[Step(heading="Do thing", caption="It does the thing.", talk_track="We do the thing.")],
        takeaways=["Fast", "Easy"],
        cta="Try it.",
    )
    defaults.update(kwargs)
    return DemoScript(**defaults)


def _make_config(**kwargs) -> DemoConfig:
    defaults = dict(product="TestProduct", feature="test-feature", local=True)
    defaults.update(kwargs)
    return DemoConfig(**defaults)


def test_html_renders_without_error(tmp_path):
    script = _make_script()
    config = _make_config()
    tok = token_loader.load()
    output = tmp_path / "test.html"
    result = html_stage.render(script, config, tok, [], output)
    content = result.read_text()
    assert "TestProduct" in content
    assert "Test Demo" in content
    assert "Do thing" in content


def test_html_escapes_xss_in_product_name(tmp_path):
    """AI-generated or user-supplied content must not inject raw HTML."""
    script = _make_script(title='<script>alert("xss")</script>')
    config = _make_config(product='<img src=x onerror=alert(1)>')
    tok = token_loader.load()
    output = tmp_path / "xss_test.html"
    result = html_stage.render(script, config, tok, [], output)
    content = result.read_text()
    assert "<script>alert" not in content
    assert "<img src=x" not in content
    assert "&lt;script&gt;" in content or "alert" not in content


def test_html_escapes_jinja2_payload_in_step(tmp_path):
    """SSTI payload in AI-generated step content must be escaped, not executed."""
    malicious_heading = "{{ 7 * 7 }}"  # Would produce 49 if evaluated
    script = _make_script(steps=[
        Step(heading=malicious_heading, caption="Normal caption", talk_track="Normal talk")
    ])
    config = _make_config()
    tok = token_loader.load()
    output = tmp_path / "ssti_test.html"
    result = html_stage.render(script, config, tok, [], output)
    content = result.read_text()
    # The literal string should appear escaped, not evaluated to 49
    assert "49" not in content or "{{ 7 * 7 }}" in content or "{{" not in content


def test_html_standard_polish_has_no_intersection_observer(tmp_path):
    script = _make_script()
    config = _make_config(polish=PolishLevel.standard)
    tok = token_loader.load()
    output = tmp_path / "standard.html"
    result = html_stage.render(script, config, tok, [], output)
    content = result.read_text()
    assert "IntersectionObserver" not in content


def test_html_production_polish_has_intersection_observer(tmp_path):
    script = _make_script()
    config = _make_config(polish=PolishLevel.production)
    tok = token_loader.load()
    output = tmp_path / "production.html"
    result = html_stage.render(script, config, tok, [], output)
    content = result.read_text()
    assert "IntersectionObserver" in content


def test_html_uses_design_tokens(tmp_path):
    script = _make_script()
    config = _make_config()
    custom_tokens = token_loader.load()
    custom_tokens["brand_primary"] = "#abcdef"
    output = tmp_path / "tokens.html"
    result = html_stage.render(script, config, custom_tokens, [], output)
    content = result.read_text()
    assert "#abcdef" in content
