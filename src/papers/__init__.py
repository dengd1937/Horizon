"""Research-paper source contracts."""

from .contract import PaperValidationError, ResearchPaper, load_paper, load_papers

__all__ = ["PaperValidationError", "ResearchPaper", "load_paper", "load_papers"]
