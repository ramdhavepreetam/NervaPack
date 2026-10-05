class Nervapack < Formula
  # Provides virtualenv_create. Without it `brew install` dies with
  # NoMethodError: undefined method 'virtualenv_create' — brew audit does not
  # catch this, since it never runs the install block.
  include Language::Python::Virtualenv

  desc "Privacy-first, offline knowledge graph for developers"
  homepage "https://github.com/ramdhavepreetam/NervaPack"
  # Use the canonical "Source" URL from https://pypi.org/project/nervapack/#files
  # (brew audit rejects the /packages/source/ redirect form).
  url "https://files.pythonhosted.org/packages/6a/7f/6b898934ee3fa020d34840452764e91c97771334d72fa6db195f34a102d9/nervapack-0.8.1.tar.gz"
  sha256 "b3f8b7faf620b4e029df6fd68433ab88257fa8329ea93eed327b417a2796b1ac"
  license "MIT"

  depends_on "python@3.12"

  # The venv's prebuilt extensions (orjson, onnxruntime, ...) carry @rpath
  # dylib IDs. Rewriting them to keg paths fails outright for orjson
  # (HeaderPadError, so `brew install` exits 1) and leaves the rest with
  # invalid signatures that Apple silicon SIGKILLs on import.
  preserve_rpath

  def install
    virtualenv_create(libexec, "python3.12")
    # Install WITH dependencies from PyPI. `venv.pip_install` passes --no-deps,
    # which produced a venv holding only nervapack and a binary that died with
    # ModuleNotFoundError. Pinned `resource` blocks are the homebrew-core way,
    # but chromadb's tree includes onnxruntime, which publishes no sdist.
    system libexec/"bin/python", "-m", "pip", "install", "--no-cache-dir", buildpath
    # CLI plus the two MCP servers and the memory CLI (all console_scripts).
    %w[nervapack nervapack-mcp nervapack-memory nervapack-memory-mcp].each do |script|
      bin.install_symlink libexec/"bin/#{script}"
    end
  end

  # preserve_rpath doesn't cover extensions with non-@rpath IDs (grpc,
  # uvloop, charset_normalizer, ...): Homebrew still rewrites those after
  # `install` and leaves them with invalid signatures, so re-sign ad hoc.
  post_install_steps do
    on_macos do
      run "/usr/bin/find",
          args:           ["{{libexec}}/lib", "(", "-name", "*.so", "-o", "-name", "*.dylib", ")",
                           "-exec", "/usr/bin/codesign", "--force", "--sign", "-", "{}", "+"],
          writable_paths: ["lib"],
          writable_base:  :libexec
    end
  end

  test do
    assert_match "NervaPack", shell_output("#{bin}/nervapack --help")
    # Imports the heavy dependencies, which --help alone never touches.
    system libexec/"bin/python", "-c", "import chromadb, tree_sitter, networkx; import nervapack.cli"
  end
end
