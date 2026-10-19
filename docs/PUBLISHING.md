# Publishing / restoring the public demonstration

Target repository: `khachatryann/solartrack-lab` (public, separate from OpenCore Lab).

The website is a plain static build. GitHub Actions verifies the numerical model, data consistency and browser behavior before publishing it to GitHub Pages.

If starting from this delivered folder without a remote:

```sh
git init -b main
git add .
git commit -m "Build reproducible SolarTrack Lab simulation and dashboard"
gh repo create solartrack-lab --public --source . --remote origin --push
gh api --method POST repos/khachatryann/solartrack-lab/pages -f build_type=workflow
gh workflow run verify-deploy.yml
```

When the repository already exists, do not create or overwrite another repository. Push the completed commit to its main branch and check Settings → Pages → Source → GitHub Actions. An already-configured Pages endpoint uses `PUT` rather than `POST` if changing its build type.

```sh
gh run list --workflow verify-deploy.yml --limit 3
gh run view RUN_ID --log-failed
```

The public URL is [khachatryann.github.io/solartrack-lab](https://khachatryann.github.io/solartrack-lab/). Confirm a successful deployment and open the page. Check a scenario change, a real tuning change and a CSV download. A successful local build alone does not verify public publication. The delivery record in `docs/DELIVERY.md` states what was actually published and checked.

After deployment, `node scripts/verify_public.cjs` exercises the public URL, actual configuration metrics, CSV download, mobile playback and methodology link. It writes `docs/public-qa.json` only after all public checks pass. This is separate from the workflow's local-build browser checks.
