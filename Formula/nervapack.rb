class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/70/55/672e473a45c8a25caa4b6d30c485e69f0e5659eebdf9c10409af5cca9ec1/nervapack-0.7.4.tar.gz"
  sha256 "2d11dfd0939d3fe5349c6a2d9cb7468dd4b196bb76625acc30c9f670edf745e5"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath
    # CLI plus the two MCP servers and the memory CLI (all console_scripts).
    %w[nervapack nervapack-mcp nervapack-memory nervapack-memory-mcp].each do |script|
      bin.install_symlink libexec/"bin/#{script}"
    end
  end

  test do
    assert_match "NervaPack", shell_output("#{bin}/nervapack --help")
  end
end
