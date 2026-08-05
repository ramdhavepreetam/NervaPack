class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/8d/67/513e59157f37328636025abfd32682b3d498447475ca32a4c94d9bddf042/nervapack-0.7.7.tar.gz"
  sha256 "fab02538e6639c79a9028c63da7acc991a65ad168cb4d89b55c1cb417bf44907"
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
