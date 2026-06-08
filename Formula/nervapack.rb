class Nervapack < Formula
  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Update url and sha256 after running: pip download nervapack==<ver> --no-deps --no-binary :all:
  # then: shasum -a 256 nervapack-<ver>.tar.gz
  url "https://files.pythonhosted.org/packages/source/n/nervapack/nervapack-0.2.0.tar.gz"
  sha256 "89c0a99b7f6d0cc849e4ea11149dbd5366fcda46e85ae111dec5cc41a2309bd7"
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
