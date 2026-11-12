from pathlib import Path
import subprocess


APP_JS = Path(__file__).parents[1] / "app/static/app.js"


def test_impugnation_modal_uses_validated_url_and_status_fallback():
    source = APP_JS.read_text()
    assert "const infoUrl = safeHttpUrl(item.impugnation_url);" in source
    assert "html(item.impugnation_url)" not in source
    assert "html(item.impugnation_status)" in source


def test_impugnation_url_validator_accepts_http_and_rejects_other_schemes():
    source = APP_JS.read_text()
    start = source.index("  function safeHttpUrl")
    end = source.index("  const date =", start)
    helper = source[start:end]
    script = f"""
{helper}
const cases = [
  ["https://cnetmobile.estaleiro.serpro.gov.br/quadro", true],
  ["http://example.test/quadro", true],
  ["javascript:alert(1)", false],
  ["data:text/html,<script>alert(1)</script>", false],
  ["//example.test/quadro", false],
  ["not a url", false],
  ["", false],
  [null, false],
];
for (const [value, valid] of cases) {{
  const result = safeHttpUrl(value);
  if ((result !== "") !== valid) throw new Error(String(value));
  if (valid && !/^https?:\\/\\//i.test(result)) throw new Error(result);
}}
"""
    subprocess.run(["node", "--input-type=module", "-e", script], check=True)
