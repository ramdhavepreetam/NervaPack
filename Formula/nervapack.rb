class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/c6/53/50994e12b2a9ab9a6401212b84fb176c7c9a392416671a41b2a3defb1e02/nervapack-0.7.6.tar.gz"
  sha256 "56275c76ba15e0bcead871b0f4ef15b45b3cdf4c9fb56fefcb9f3ca685110460"
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
