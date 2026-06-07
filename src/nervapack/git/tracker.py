import git
from typing import List

class GitTracker:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        try:
            self.repo = git.Repo(self.repo_path)
        except git.InvalidGitRepositoryError:
            self.repo = None

    def get_changed_files(self, commit_sha: str = None) -> List[str]:
        """
        Gets a list of modified files.
        If commit_sha is provided, diffs against that.
        Otherwise diffs the working tree against HEAD.
        """
        if not self.repo:
            return []

        changed_files = []
        
        if commit_sha:
            try:
                commit = self.repo.commit(commit_sha)
                diffs = commit.diff(commit.parents[0] if commit.parents else None)
                for diff in diffs:
                    changed_files.append(diff.b_path or diff.a_path)
            except Exception:
                pass
        else:
            # Diff working tree against HEAD
            diffs = self.repo.index.diff(None)
            for diff in diffs:
                changed_files.append(diff.b_path or diff.a_path)
                
            # Staged diffs
            staged_diffs = self.repo.index.diff("HEAD")
            for diff in staged_diffs:
                changed_files.append(diff.b_path or diff.a_path)

            # Untracked files
            changed_files.extend(self.repo.untracked_files)

        # Remove duplicates
        return list(set(changed_files))
