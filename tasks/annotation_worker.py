"""CouchDB changes-feed worker that annotates new articles with AI.

Watches the ``articles`` database for documents without an ``annotations``
field, calls the LLM annotator, and writes the result back to the document.
Follows the same pattern as :class:`EnrichmentWorker`.
"""

import threading
import time
import requests
import logging
from api.db_config import get_couchdb_uri
from .annotator import annotate_article, store_annotation

logger = logging.getLogger(__name__)


class AnnotationWorker(threading.Thread):
    """Daemon thread that listens to the CouchDB ``articles`` changes feed
    and annotates new/un-annotated articles via the configured LLM provider.
    """

    def __init__(self) -> None:
        threading.Thread.__init__(self)
        self.daemon = True
        self.db_name = "articles"
        self.last_seq = "0"
        self.running = True

    @property
    def couchdb_url(self) -> str:
        return get_couchdb_uri()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info("AnnotationWorker started.")
        self.last_seq = self._get_last_seq()

        while self.running:
            self._process_changes()

    # ------------------------------------------------------------------
    # Sequence tracking
    # ------------------------------------------------------------------

    def _get_last_seq(self) -> str:
        """Get the last processed sequence from the config DB."""
        try:
            res = requests.get(
                f"{self.couchdb_url}config/annotation_last_seq", timeout=10
            )
            if res.status_code == 200:
                return res.json().get("value", "0")
            if res.status_code != 404:
                logger.error(
                    f"AnnotationWorker: unexpected status {res.status_code} loading last_seq"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AnnotationWorker: failed to load last_seq: {e}")
        except ValueError as e:
            logger.error(f"AnnotationWorker: invalid last_seq response: {e}")
        return "now"

    def _save_last_seq(self, seq: str) -> None:
        """Save the last processed sequence to the config DB."""
        try:
            doc = {"_id": "annotation_last_seq", "value": seq}
            res = requests.get(
                f"{self.couchdb_url}config/annotation_last_seq", timeout=10
            )
            if res.status_code == 200:
                doc["_rev"] = res.json()["_rev"]
            elif res.status_code != 404:
                logger.error(
                    f"AnnotationWorker: unexpected status {res.status_code} reading last_seq"
                )
            res = requests.put(
                f"{self.couchdb_url}config/annotation_last_seq", json=doc, timeout=10
            )
            if res.status_code not in (200, 201):
                logger.error(
                    f"AnnotationWorker: failed to save last_seq: "
                    f"{res.status_code} {res.text}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AnnotationWorker: failed to save last_seq: {e}")
        except ValueError as e:
            logger.error(f"AnnotationWorker: invalid last_seq response: {e}")

    # ------------------------------------------------------------------
    # Changes feed processing
    # ------------------------------------------------------------------

    def _process_changes(self) -> None:
        """Long-poll the CouchDB changes feed and annotate new articles."""
        changes_url = f"{self.couchdb_url}{self.db_name}/_changes"
        params = {
            "feed": "longpoll",
            "since": self.last_seq,
            "include_docs": "true",
            "timeout": 30000,
        }

        try:
            response = requests.get(changes_url, params=params, timeout=35)
        except requests.exceptions.RequestException as e:
            logger.error(f"AnnotationWorker: changes feed error: {e}")
            time.sleep(5)
            return

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"AnnotationWorker: invalid changes response: {e}")
                time.sleep(5)
                return

            results = data.get("results", [])

            for change in results:
                doc = change.get("doc")
                if not doc or doc.get("_id", "").startswith("_design/"):
                    continue

                self._maybe_annotate(doc)

            if data.get("last_seq"):
                self.last_seq = data["last_seq"]
                self._save_last_seq(self.last_seq)

        elif response.status_code == 404:
            # DB doesn't exist yet — wait and retry
            time.sleep(10)
        else:
            logger.error(
                f"AnnotationWorker: Unexpected status {response.status_code}"
            )
            time.sleep(10)

    def _maybe_annotate(self, doc: dict) -> None:
        """Annotate an article document if it has no annotations yet."""
        if "annotations" in doc:
            return  # Already annotated

        article_id = doc.get("_id", "")
        title = doc.get("title", "")
        summary = doc.get("summary", "") or doc.get("description", "")

        if not title:
            return  # Nothing useful to annotate

        logger.info(f"Annotating article: {title[:80]}")

        annotation = annotate_article(title, summary)
        if annotation is None:
            logger.warning(f"Annotation failed for article {article_id}")
            return

        success = store_annotation(article_id, annotation)
        if success:
            logger.info(
                f"Annotated {article_id}: topics={annotation['topics']}, "
                f"priority={annotation['priority']}, sentiment={annotation['sentiment']}"
            )
        else:
            logger.error(f"Failed to store annotation for {article_id}")


# Global instance
annotation_worker = AnnotationWorker()
