class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Update url and sha256 after running: pip download nervapack==<ver> --no-deps --no-binary :all:
  # then: shasum -a 256 nervapack-<ver>.tar.gz
  url "https://files.pythonhosted.org/packages/source/n/nervapack/nervapack-0.1.0.tar.gz"
  sha256 "b390f43c82d6c4fa3ad6114270c6ea4632c4ddb520ff33efb8769d05182fab3b"
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath
    bin.install_symlink libexec/"bin/nervapack"
  end

  test do
    assert_match "NervaPack", shell_output("#{bin}/nervapack --help")
  end
end
