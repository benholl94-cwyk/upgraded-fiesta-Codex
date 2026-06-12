"""
Tests for documentation content changed in the PR:
  - README.md: updated date, expanded Schwerpunkt topics, expanded last sentence
  - docs/iphone-local-dev-setup.md: updated date, new sections 10.1/10.3/11,
    renumbered sections, two new checklist items
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
README = REPO_ROOT / "README.md"
GUIDE = REPO_ROOT / "docs" / "iphone-local-dev-setup.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestReadmeChanges(unittest.TestCase):
    """Tests for changes made to README.md in this PR."""

    def setUp(self):
        self.text = _read(README)

    # --- date ---

    def test_readme_date_updated_to_2026_06_12(self):
        """Stand field must reflect the updated date 2026-06-12."""
        self.assertIn("2026-06-12", self.text)

    def test_readme_old_date_not_present(self):
        """Old date 2026-06-11 must not appear in README."""
        self.assertNotIn("2026-06-11", self.text)

    # --- Schwerpunkt bullet ---

    def test_readme_schwerpunkt_contains_localhost(self):
        """Schwerpunkt bullet must mention Localhost."""
        self.assertIn("Localhost", self.text)

    def test_readme_schwerpunkt_contains_internet_grundlagen(self):
        """Schwerpunkt bullet must mention Internet-Grundlagen."""
        self.assertIn("Internet-Grundlagen", self.text)

    def test_readme_schwerpunkt_bullet_full_topics(self):
        """Schwerpunkt bullet must list all expected topics in correct order."""
        line = next(
            (l for l in self.text.splitlines() if l.startswith("- Schwerpunkt:")),
            None,
        )
        self.assertIsNotNone(line, "Schwerpunkt bullet not found")
        expected_topics = [
            "lokale Shell",
            "Git-Workflow",
            "Editor",
            "Python/JavaScript",
            "Localhost",
            "Internet-Grundlagen",
            "SSH",
            "Backups",
            "Wartung",
        ]
        for topic in expected_topics:
            self.assertIn(topic, line, f"Topic '{topic}' missing from Schwerpunkt bullet")

    # --- last sentence ---

    def test_readme_last_sentence_contains_localhost_variablen(self):
        """Last sentence must mention Localhost-Variablen."""
        self.assertIn("Localhost-Variablen", self.text)

    def test_readme_last_sentence_contains_internet_grundlagen(self):
        """Last sentence must mention Internet-Grundlagen in context of full guide."""
        # The phrase appears in the last paragraph linking to the full guide.
        last_para_match = re.search(
            r"Die Details.*?Fehlerbehebung stehen in der vollständigen Anleitung\.",
            self.text,
            re.DOTALL,
        )
        self.assertIsNotNone(last_para_match, "Closing sentence paragraph not found")
        self.assertIn("Internet-Grundlagen", last_para_match.group())

    def test_readme_last_sentence_contains_testbefehlen(self):
        """Last sentence must still mention Testbefehlen (pre-existing content)."""
        self.assertIn("Testbefehlen", self.text)

    def test_readme_link_to_guide_intact(self):
        """Link to docs/iphone-local-dev-setup.md must be present."""
        self.assertIn("docs/iphone-local-dev-setup.md", self.text)

    # --- negative / boundary ---

    def test_readme_has_no_trailing_whitespace_on_changed_lines(self):
        """Changed lines must not introduce trailing whitespace."""
        offending = [
            l
            for l in self.text.splitlines()
            if ("Localhost" in l or "Internet-Grundlagen" in l) and l != l.rstrip()
        ]
        self.assertEqual(offending, [], f"Lines with trailing whitespace: {offending}")


class TestGuideDate(unittest.TestCase):
    """Tests for the date header change in iphone-local-dev-setup.md."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_guide_date_updated_to_2026_06_12(self):
        """Stand field must reflect 2026-06-12."""
        self.assertIn("Stand: 2026-06-12", self.text)

    def test_guide_old_date_not_present(self):
        """Old date 2026-06-11 must not appear in guide."""
        self.assertNotIn("2026-06-11", self.text)


class TestGuideSection10_1_LocalhostVariables(unittest.TestCase):
    """Tests for the new section 10.1 (Sinnvolle Localhost-Variablen)."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_section_10_1_heading_present(self):
        """Section heading '### 10.1 Sinnvolle Localhost-Variablen' must exist."""
        self.assertIn("### 10.1 Sinnvolle Localhost-Variablen", self.text)

    def test_profile_snippet_exports_dev_host(self):
        """Profile snippet must export DEV_HOST=127.0.0.1."""
        self.assertIn("export DEV_HOST=127.0.0.1", self.text)

    def test_profile_snippet_exports_dev_bind(self):
        """Profile snippet must export DEV_BIND=127.0.0.1."""
        self.assertIn("export DEV_BIND=127.0.0.1", self.text)

    def test_profile_snippet_exports_dev_port(self):
        """Profile snippet must export DEV_PORT=8000."""
        self.assertIn("export DEV_PORT=8000", self.text)

    def test_profile_snippet_exports_dev_alt_port(self):
        """Profile snippet must export DEV_ALT_PORT=3000."""
        self.assertIn("export DEV_ALT_PORT=3000", self.text)

    def test_profile_snippet_exports_dev_url(self):
        """Profile snippet must export DEV_URL referencing DEV_HOST and DEV_PORT."""
        self.assertIn('export DEV_URL="http://${DEV_HOST}:${DEV_PORT}"', self.text)

    def test_profile_snippet_exports_localhost_url(self):
        """Profile snippet must export LOCALHOST_URL."""
        self.assertIn("export LOCALHOST_URL", self.text)

    def test_profile_snippet_exports_no_proxy_uppercase(self):
        """Profile snippet must export NO_PROXY for proxy bypass."""
        self.assertIn('export NO_PROXY="localhost,127.0.0.1,::1,*.local"', self.text)

    def test_profile_snippet_exports_no_proxy_lowercase(self):
        """Profile snippet must export lowercase no_proxy alias."""
        self.assertIn('export no_proxy="$NO_PROXY"', self.text)

    def test_profile_snippet_exports_pythonunbuffered(self):
        """Profile snippet must export PYTHONUNBUFFERED=1."""
        self.assertIn("export PYTHONUNBUFFERED=1", self.text)

    def test_profile_snippet_exports_pip_disable_version_check(self):
        """Profile snippet must export PIP_DISABLE_PIP_VERSION_CHECK=1."""
        self.assertIn("export PIP_DISABLE_PIP_VERSION_CHECK=1", self.text)

    def test_profile_snippet_exports_npm_config_audit(self):
        """Profile snippet must export npm_config_audit=false."""
        self.assertIn("export npm_config_audit=false", self.text)

    def test_profile_snippet_exports_npm_config_fund(self):
        """Profile snippet must export npm_config_fund=false."""
        self.assertIn("export npm_config_fund=false", self.text)

    def test_network_bind_example_uses_0_0_0_0(self):
        """Network-bind example must show 0.0.0.0 as the alternative bind address."""
        self.assertIn("export DEV_BIND=0.0.0.0", self.text)

    def test_variable_table_contains_dev_host_row(self):
        """Variable table must contain a row for DEV_HOST."""
        self.assertIn("| `DEV_HOST`", self.text)

    def test_variable_table_contains_dev_bind_row(self):
        """Variable table must contain a row for DEV_BIND."""
        self.assertIn("| `DEV_BIND`", self.text)

    def test_variable_table_contains_dev_port_row(self):
        """Variable table must contain a row for DEV_PORT."""
        self.assertIn("| `DEV_PORT`", self.text)

    def test_variable_table_contains_dev_alt_port_row(self):
        """Variable table must contain a row for DEV_ALT_PORT."""
        self.assertIn("| `DEV_ALT_PORT`", self.text)

    def test_variable_table_contains_dev_url_row(self):
        """Variable table must contain a row for DEV_URL."""
        self.assertIn("| `DEV_URL`", self.text)

    def test_variable_table_contains_no_proxy_row(self):
        """Variable table must contain a row for NO_PROXY/no_proxy."""
        self.assertIn("`NO_PROXY`/`no_proxy`", self.text)

    def test_variable_table_contains_http_proxy_row(self):
        """Variable table must document HTTP_PROXY/HTTPS_PROXY."""
        self.assertIn("`HTTP_PROXY`/`HTTPS_PROXY`", self.text)

    def test_variable_table_contains_ssl_cert_file_row(self):
        """Variable table must document SSL_CERT_FILE/REQUESTS_CA_BUNDLE."""
        self.assertIn("`SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`", self.text)

    def test_variable_table_contains_curl_ca_bundle_row(self):
        """Variable table must document CURL_CA_BUNDLE/GIT_SSL_CAINFO."""
        self.assertIn("`CURL_CA_BUNDLE`/`GIT_SSL_CAINFO`", self.text)

    def test_guidance_127_vs_0_0_0_0(self):
        """Section must explain when to use 127.0.0.1 vs 0.0.0.0."""
        self.assertIn("127.0.0.1", self.text)
        self.assertIn("0.0.0.0", self.text)
        self.assertIn("dem Netzwerk vertraust", self.text)


class TestGuideSection10_2_LocalServerUpdate(unittest.TestCase):
    """Tests for changes to section 10.2 (Lokalen Server starten)."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_section_10_2_heading_present(self):
        """Section heading '### 10.2 Lokalen Server starten' must exist."""
        self.assertIn("### 10.2 Lokalen Server starten", self.text)

    def test_server_command_uses_dev_port_variable(self):
        """http.server invocation must use $DEV_PORT variable."""
        self.assertIn('"$DEV_PORT"', self.text)

    def test_server_command_uses_dev_bind_variable(self):
        """http.server invocation must use $DEV_BIND variable."""
        self.assertIn('"$DEV_BIND"', self.text)

    def test_browser_url_includes_127_0_0_1(self):
        """Browser URL section must include http://127.0.0.1:8000 as alternative."""
        self.assertIn("http://127.0.0.1:8000", self.text)

    def test_hint_localhost_fallback_to_127(self):
        """Hints must advise falling back from localhost to 127.0.0.1."""
        self.assertIn(
            "Wenn `localhost` nicht funktioniert, teste `http://127.0.0.1:8000`",
            self.text,
        )

    def test_hint_port_conflict_advice(self):
        """Hints must advise changing DEV_PORT when port is occupied."""
        self.assertIn("Wenn ein Port belegt ist", self.text)


class TestGuideSection10_3_NetworkDiagnostics(unittest.TestCase):
    """Tests for the new section 10.3 (Netzwerkdiagnose für Localhost)."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_section_10_3_heading_present(self):
        """Section heading '### 10.3 Netzwerkdiagnose für Localhost' must exist."""
        self.assertIn("### 10.3 Netzwerkdiagnose für Localhost", self.text)

    def test_diagnostics_snippet_uses_dev_url(self):
        """Diagnostics snippet must use $DEV_URL."""
        self.assertIn('"$DEV_URL"', self.text)

    def test_error_connection_refused_documented(self):
        """Error 'Connection refused' must be documented."""
        self.assertIn("Connection refused", self.text)

    def test_error_timeout_documented(self):
        """Error 'Timeout' must be documented."""
        self.assertIn("Timeout", self.text)

    def test_error_404_documented(self):
        """Error '404' must be documented."""
        self.assertIn("`404`", self.text)

    def test_error_ssl_certificate_problem_documented(self):
        """Error 'SSL certificate problem' must be documented."""
        self.assertIn("SSL certificate problem", self.text)


class TestGuideSection11_InternetBasics(unittest.TestCase):
    """Tests for the new section 11 (Internet-Grundlagen und Online-Arbeit)."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_section_11_heading_present(self):
        """Top-level heading '## 11. Internet-Grundlagen...' must exist."""
        self.assertIn("## 11. Internet-Grundlagen und Online-Arbeit", self.text)

    def test_concept_ip_address_explained(self):
        """Section must explain IP-Adresse."""
        self.assertIn("**IP-Adresse**", self.text)

    def test_concept_dns_explained(self):
        """Section must explain DNS."""
        self.assertIn("**DNS**", self.text)

    def test_concept_http_https_explained(self):
        """Section must explain HTTP/HTTPS."""
        self.assertIn("**HTTP/HTTPS**", self.text)

    def test_concept_url_explained(self):
        """Section must explain URL."""
        self.assertIn("**URL**", self.text)

    def test_concept_port_explained(self):
        """Section must explain Port."""
        self.assertIn("**Port**", self.text)

    def test_concept_tls_certificate_explained(self):
        """Section must explain TLS-Zertifikat."""
        self.assertIn("**TLS-Zertifikat**", self.text)

    def test_concept_cookies_tokens_sessions_explained(self):
        """Section must explain Cookies, Tokens und Sessions."""
        self.assertIn("**Cookies, Tokens und Sessions**", self.text)

    def test_concept_api_explained(self):
        """Section must explain API."""
        self.assertIn("**API**", self.text)

    def test_concept_cdn_cache_explained(self):
        """Section must explain CDN und Cache."""
        self.assertIn("**CDN und Cache**", self.text)

    # Section 11.1
    def test_section_11_1_heading_present(self):
        """Sub-heading '### 11.1 Verbindung prüfen' must exist."""
        self.assertIn("### 11.1 Verbindung prüfen", self.text)

    def test_section_11_1_curl_example_present(self):
        """Section 11.1 must include a curl -I example."""
        self.assertIn("curl -I https://example.com", self.text)

    def test_section_11_1_socket_python_example_present(self):
        """Section 11.1 must include a Python socket.gethostbyname example."""
        self.assertIn("socket.gethostbyname", self.text)

    def test_section_11_1_troubleshooting_mentions_vpn(self):
        """Troubleshooting list must mention VPN."""
        self.assertIn("VPN", self.text)

    def test_section_11_1_troubleshooting_mentions_datetime(self):
        """Troubleshooting list must mention date/time and certificate checks."""
        self.assertIn("Datum/Uhrzeit", self.text)

    # Section 11.2
    def test_section_11_2_heading_present(self):
        """Sub-heading '### 11.2 Sicher herunterladen' must exist."""
        self.assertIn("### 11.2 Sicher herunterladen", self.text)

    def test_section_11_2_curl_download_example(self):
        """Section 11.2 must show curl -L -o download pattern."""
        self.assertIn("curl -L -o datei.zip", self.text)

    def test_section_11_2_zip_verify_example(self):
        """Section 11.2 must show python3 -m zipfile -t verify pattern."""
        self.assertIn("python3 -m zipfile -t datei.zip", self.text)

    def test_section_11_2_warns_against_curl_pipe_sh(self):
        """Section 11.2 must warn against curl ... | sh pattern."""
        self.assertIn("curl ... | sh", self.text)

    def test_section_11_2_advises_separating_secrets(self):
        """Section 11.2 must advise separating tokens/keys from public repos."""
        self.assertIn("Trenne private Tokens", self.text)

    # Section 11.3
    def test_section_11_3_heading_present(self):
        """Sub-heading '### 11.3 APIs nutzen' must exist."""
        self.assertIn("### 11.3 APIs nutzen", self.text)

    def test_section_11_3_api_curl_example(self):
        """Section 11.3 must show a curl API test example."""
        self.assertIn("curl -s https://api.github.com", self.text)

    def test_section_11_3_token_read_pattern(self):
        """Section 11.3 must show read -r API_TOKEN / unset API_TOKEN pattern."""
        self.assertIn("read -r API_TOKEN", self.text)
        self.assertIn("unset API_TOKEN", self.text)

    def test_section_11_3_status_code_200(self):
        """`200` success must be documented."""
        self.assertIn("`200`", self.text)

    def test_section_11_3_status_code_201(self):
        """`201` created must be documented."""
        self.assertIn("`201`", self.text)

    def test_section_11_3_status_code_301_302(self):
        """`301/302` redirect must be documented."""
        self.assertIn("`301/302`", self.text)

    def test_section_11_3_status_code_400(self):
        """`400` bad request must be documented."""
        self.assertIn("`400`", self.text)

    def test_section_11_3_status_code_401(self):
        """`401` unauthorized must be documented."""
        self.assertIn("`401`", self.text)

    def test_section_11_3_status_code_403(self):
        """`403` forbidden/rate-limit must be documented."""
        self.assertIn("`403`", self.text)

    def test_section_11_3_status_code_404(self):
        """`404` not found must be documented in API rules."""
        # 404 appears both in 10.3 and 11.3
        count = self.text.count("`404`")
        self.assertGreaterEqual(count, 1)

    def test_section_11_3_status_code_429(self):
        """`429` too many requests must be documented."""
        self.assertIn("`429`", self.text)

    def test_section_11_3_status_code_500(self):
        """`500` server error must be documented."""
        self.assertIn("`500`", self.text)

    def test_section_11_3_http_methods_get_post_put_delete(self):
        """HTTP methods GET, POST, PUT/PATCH, DELETE must be documented."""
        self.assertIn("`GET`", self.text)
        self.assertIn("`POST`", self.text)
        self.assertIn("`PUT/PATCH`", self.text)
        self.assertIn("`DELETE`", self.text)

    def test_section_11_3_secrets_storage_advice(self):
        """Section 11.3 must advise against storing secrets in Git."""
        self.assertIn("nicht in Git", self.text)

    # Section 11.4
    def test_section_11_4_heading_present(self):
        """Sub-heading '### 11.4 Web-Recherche und Quellenbewertung' must exist."""
        self.assertIn("### 11.4 Web-Recherche und Quellenbewertung", self.text)

    def test_section_11_4_advises_primary_sources(self):
        """Section 11.4 must advise using primary sources."""
        self.assertIn("Primärquellen", self.text)

    # Section 11.5
    def test_section_11_5_heading_present(self):
        """Sub-heading '### 11.5 Privatsphäre und Sicherheit im Internet' must exist."""
        self.assertIn("### 11.5 Privatsphäre und Sicherheit im Internet", self.text)

    def test_section_11_5_advises_2fa_mfa(self):
        """Section 11.5 must advise activating 2FA/MFA."""
        self.assertIn("2FA/MFA", self.text)

    def test_section_11_5_vpn_not_replace_https(self):
        """Section 11.5 must state that VPN does not replace HTTPS."""
        self.assertIn("ein VPN ersetzt kein HTTPS", self.text)


class TestGuideSectionRenumbering(unittest.TestCase):
    """Tests that pre-existing sections were correctly renumbered."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_section_12_remote_ergaenzung(self):
        """Remote-Ergänzung section must now be numbered 12."""
        self.assertIn("## 12. Remote-Ergänzung für große Projekte", self.text)

    def test_section_11_not_remote_ergaenzung(self):
        """Section 11 must NOT be Remote-Ergänzung (it was renumbered to 12)."""
        self.assertNotIn("## 11. Remote-Ergänzung", self.text)

    def test_section_13_sicherheit(self):
        """Sicherheit section must now be numbered 13."""
        self.assertIn("## 13. Sicherheit", self.text)

    def test_section_12_not_sicherheit(self):
        """Section 12 must NOT be Sicherheit (it was renumbered to 13)."""
        self.assertNotIn("## 12. Sicherheit", self.text)

    def test_section_14_backup_strategie(self):
        """Backup-Strategie section must now be numbered 14."""
        self.assertIn("## 14. Backup-Strategie", self.text)

    def test_section_15_wartung(self):
        """Wartung section must now be numbered 15."""
        self.assertIn("## 15. Wartung", self.text)

    def test_section_16_fehlerbehebung(self):
        """Fehlerbehebung section must now be numbered 16."""
        self.assertIn("## 16. Fehlerbehebung", self.text)

    def test_section_17_minimal_checkliste(self):
        """Minimal-Checkliste section must now be numbered 17."""
        self.assertIn("## 17. Minimal-Checkliste", self.text)

    def test_section_18_empfohlene_startkonfiguration(self):
        """Empfohlene Startkonfiguration section must now be numbered 18."""
        self.assertIn("## 18. Empfohlene Startkonfiguration", self.text)


class TestGuideChecklistNewItems(unittest.TestCase):
    """Tests for the two new checklist items in section 17."""

    def setUp(self):
        self.text = _read(GUIDE)

    def test_checklist_localhost_variables_item(self):
        """Checklist must include localhost variables item."""
        self.assertIn(
            "- [ ] Localhost-Variablen gesetzt und `http://127.0.0.1:8000` getestet.",
            self.text,
        )

    def test_checklist_internet_api_basics_item(self):
        """Checklist must include internet/API basics item."""
        self.assertIn(
            "- [ ] Internet-/API-Grundlagen mit `curl -I https://example.com` geprüft.",
            self.text,
        )

    def test_checklist_localhost_item_before_testaenderung(self):
        """Localhost checklist item must appear before 'Teständerung committet' item."""
        idx_localhost = self.text.index(
            "- [ ] Localhost-Variablen gesetzt und `http://127.0.0.1:8000` getestet."
        )
        idx_test = self.text.index("- [ ] Teständerung committet und gepusht.")
        self.assertLess(idx_localhost, idx_test)

    def test_checklist_internet_item_before_testaenderung(self):
        """Internet/API checklist item must appear before 'Teständerung committet' item."""
        idx_internet = self.text.index(
            "- [ ] Internet-/API-Grundlagen mit `curl -I https://example.com` geprüft."
        )
        idx_test = self.text.index("- [ ] Teständerung committet und gepusht.")
        self.assertLess(idx_internet, idx_test)

    # Regression: checklist must still contain the pre-existing items too
    def test_checklist_ios_updated_item_still_present(self):
        """Pre-existing checklist item 'iOS aktualisiert' must still be present."""
        self.assertIn("- [ ] iOS aktualisiert.", self.text)

    def test_checklist_backup_strategie_item_still_present(self):
        """Pre-existing checklist item 'Backup-Strategie festgelegt' must still be present."""
        self.assertIn("- [ ] Backup-Strategie festgelegt.", self.text)


if __name__ == "__main__":
    unittest.main()
