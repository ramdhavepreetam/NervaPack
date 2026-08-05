class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/3f/14/40018a4938426e294644926290571874a85fc658ac211fec8b0142bbace8/nervapack-0.7.5.tar.gz"
  sha256 "c4c385be357a369852c11693b6e138fbcd8c4f10725cadc88fc35d669e15f837"
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
