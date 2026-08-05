class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/bd/57/ccb9e520eba0d8e8dd33bd52ec6375a53ae69e0fbf049b87e9fc58b6d89b/nervapack-0.7.3.tar.gz"
  sha256 "e91bd0a797f635b94492153e5481c934d496d2e2ee6480e670311b4274fb2cf0"
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
