# NervaPack Documentation Deployment Guide

Your documentation site is ready to deploy! Follow these steps.

---

## ✅ What's Been Set Up

1. **MkDocs Material** configuration (`mkdocs.yml`)
2. **Documentation structure** (`docs/` folder with content)
3. **Read the Docs** configuration (`.readthedocs.yml`)
4. **Requirements file** (`docs/requirements.txt`)
5. **Essential pages**:
   - Homepage (index.md)
   - Installation guide
   - Quick start tutorial
   - LLM providers guide
   - Architecture documentation
   - Command references
   - Contributing guide
   - Changelog

---

## 🚀 Deploying to Read the Docs (FREE)

### Step 1: Push to GitHub

```bash
# Add all documentation files
git add mkdocs.yml .readthedocs.yml docs/ DOCS_DEPLOYMENT.md

# Commit
git commit -m "docs: Add MkDocs Material documentation site

- Add comprehensive documentation structure
- Configure Read the Docs integration
- Add installation, quick start, and command guides
- Add architecture and concept documentation
- Set up automatic builds on commit"

# Push to GitHub
git push origin master
```

### Step 2: Import to Read the Docs

1. **Go to:** https://readthedocs.org/
2. **Sign in** with your GitHub account
3. **Click:** "Import a Project"
4. **Select:** "ramdhavepreetam/NervaPack"
5. **Click:** "Next"
6. **Keep default settings:**
   - Name: `nervapack`
   - Repository URL: (auto-filled)
   - Default branch: `master`
7. **Click:** "Finish"

### Step 3: Build

Read the Docs will automatically:
- Detect `.readthedocs.yml`
- Install dependencies from `docs/requirements.txt`
- Build with `mkdocs.yml`
- Deploy to: **https://nervapack.readthedocs.io**

**Build time:** 2-3 minutes

### Step 4: Verify

Visit: **https://nervapack.readthedocs.io**

You should see:
- ✅ Beautiful Material theme
- ✅ Search functionality
- ✅ Navigation tabs
- ✅ Dark mode toggle
- ✅ All your documentation

---

## 🔄 Auto-Updates

Every time you push to GitHub:
1. Read the Docs detects the commit
2. Automatically rebuilds the docs
3. Deploys updates in 2-3 minutes
4. **Zero manual work required!**

---

## 🧪 Testing Locally

Before pushing, test the docs locally:

```bash
# Install dependencies (one-time)
pip install mkdocs-material "mkdocstrings[python]" pymdown-extensions mkdocs-minify-plugin

# Serve locally
mkdocs serve

# Opens at: http://localhost:8000
# Auto-reloads on file changes
```

**To stop:** Press `Ctrl+C`

---

## 📝 Adding New Pages

### 1. Create markdown file

```bash
# Example: Add a new tutorial
vim docs/tutorials/my-tutorial.md
```

### 2. Add to navigation

Edit `mkdocs.yml`:

```yaml
nav:
  - Tutorials:
    - My Tutorial: tutorials/my-tutorial.md  # Add this line
```

### 3. Test locally

```bash
mkdocs serve
```

### 4. Push to GitHub

```bash
git add docs/tutorials/my-tutorial.md mkdocs.yml
git commit -m "docs: Add my tutorial"
git push
```

**Done!** Read the Docs auto-deploys in 2-3 minutes.

---

## 🎨 Customization

### Change Colors

Edit `mkdocs.yml`:

```yaml
theme:
  palette:
    - scheme: default
      primary: blue     # Change from indigo to blue
      accent: blue
```

### Add Custom CSS

```bash
# Create custom CSS
mkdir docs/stylesheets
cat > docs/stylesheets/extra.css << 'EOF'
.md-header {
  background-color: #1976d2;
}
EOF
```

Add to `mkdocs.yml`:

```yaml
extra_css:
  - stylesheets/extra.css
```

### Add Google Analytics

Edit `mkdocs.yml`:

```yaml
extra:
  analytics:
    provider: google
    property: G-XXXXXXXXXX  # Your tracking ID
```

---

## 🌐 Custom Domain (Optional)

Want `docs.nervapack.dev` instead of `nervapack.readthedocs.io`?

### 1. Buy domain

- Namecheap: $12/year
- Google Domains: $12/year
- Cloudflare: $9/year

### 2. Add DNS record

In your domain registrar:

```
Type: CNAME
Name: docs
Value: nervapack.readthedocs.io
TTL: Auto
```

### 3. Configure Read the Docs

1. Go to: https://readthedocs.org/dashboard/nervapack/domains/
2. Click "Add custom domain"
3. Enter: `docs.nervapack.dev`
4. Click "Add"

**HTTPS is automatic!** Read the Docs generates SSL certificates.

**Cost:** Only domain registration ($9-12/year). Read the Docs hosting is FREE.

---

## 📊 Monitoring

### Check Build Status

- Dashboard: https://readthedocs.org/projects/nervapack/builds/
- Build logs: Click on any build to see logs
- Email notifications: Enabled by default on failures

### View Analytics

Read the Docs provides:
- Page views
- Search queries
- Top pages
- Referrers

Access at: https://readthedocs.org/projects/nervapack/traffic/

---

## 🐛 Troubleshooting

### Build fails

**Check build logs:**
1. Go to: https://readthedocs.org/projects/nervapack/builds/
2. Click the failed build
3. Review error messages

**Common issues:**
- Missing dependency in `docs/requirements.txt`
- Typo in `mkdocs.yml`
- Broken internal link

**Fix locally first:**
```bash
mkdocs build
# Fix any errors shown
git commit -am "docs: Fix build error"
git push
```

### Search not working

Search is automatic on Read the Docs. If it's not working:
- Wait 5 minutes after first deploy
- Hard refresh browser (Cmd+Shift+R)
- Check browser console for errors

### Page not found

1. Verify file exists in `docs/` folder
2. Check `nav` in `mkdocs.yml` has correct path
3. Rebuild locally: `mkdocs build`

---

## 📈 Next Steps

### Immediate (This Week)
- [ ] Deploy to Read the Docs (15 minutes)
- [ ] Verify site loads correctly
- [ ] Share URL with early users

### Short-term (This Month)
- [ ] Fill in stub pages (commands, concepts)
- [ ] Add more tutorials
- [ ] Add screenshots/GIFs
- [ ] Set up custom domain (optional)

### Long-term (3-6 Months)
- [ ] Add video tutorials
- [ ] Create interactive examples
- [ ] Translate to other languages
- [ ] Add community contributions

---

## 🎓 Learning Resources

- **MkDocs Material Docs:** https://squidfunk.github.io/mkdocs-material/
- **Read the Docs Guide:** https://docs.readthedocs.io/
- **Markdown Guide:** https://www.markdownguide.org/

---

## 🎉 You're Ready!

Your documentation infrastructure is production-ready:

✅ Professional theme (Material for MkDocs)
✅ Free hosting (Read the Docs)
✅ Auto-deployment (GitHub webhooks)
✅ Search, dark mode, mobile-responsive
✅ SSL/HTTPS included
✅ Comprehensive content structure

**Next action:** Push to GitHub and import to Read the Docs!

```bash
git add .
git commit -m "docs: Add complete documentation site"
git push origin master
```

Then visit: https://readthedocs.org/dashboard/ and import your project.

**Your docs will be live at:** https://nervapack.readthedocs.io

---

**Questions?** Open an issue: https://github.com/ramdhavepreetam/NervaPack/issues
