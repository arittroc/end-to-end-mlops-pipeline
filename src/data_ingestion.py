"""
data_ingestion.py
=================
Factory Design Pattern for dataset ingestion.

Architecture
------------
  DataIngestor          (ABC)           — enforces a single public contract
  ├── CSVDataIngestor                   — reads .csv files directly
  └── ZipDataIngestor                   — extracts CSV(s) from a .zip archive

  DataIngestorFactory                   — inspects the file extension at
                                          runtime and returns the correct
                                          concrete ingestor; supports dynamic
                                          registration of new formats.

Usage
-----
    from src.data_ingestion import DataIngestorFactory

    ingestor = DataIngestorFactory.get_ingestor("data/train.zip")
    df = ingestor.ingest("data/train.zip")

Notes
-----
- No model training logic lives here.
- All public methods are fully type-annotated.
- The factory registry is open for extension without modifying existing code
  (Open/Closed Principle).
"""

from __future__ import annotations

import logging
import os
import zipfile
from abc import ABC, abstractmethod
from typing import ClassVar

import pandas as pd

logger: logging.Logger = logging.getLogger(__name__)


# ── Abstract Base ──────────────────────────────────────────────────────────


class DataIngestor(ABC):
    """
    Abstract contract that every concrete ingestor must satisfy.

    All subclasses receive a file path and are responsible for returning
    a clean, in-memory ``pd.DataFrame``.  I/O concerns (format parsing,
    archive extraction) are fully encapsulated inside each subclass so the
    rest of the pipeline never needs to know *how* the data arrived.
    """

    @abstractmethod
    def ingest(self, file_path: str) -> pd.DataFrame:
        """
        Load data from *file_path* and return it as a DataFrame.

        Parameters
        ----------
        file_path : str
            Absolute or relative path to the source file.

        Returns
        -------
        pd.DataFrame
            Raw, unprocessed dataset exactly as stored on disk.

        Raises
        ------
        FileNotFoundError
            When *file_path* does not exist on the filesystem.
        ValueError
            When the file content is malformed or unreadable.
        """


# ── Concrete Ingestors ─────────────────────────────────────────────────────


class CSVDataIngestor(DataIngestor):
    """
    Ingestor for plain CSV files.

    Delegates entirely to ``pd.read_csv``; any keyword arguments accepted by
    that function can be forwarded via ``**kwargs``.

    Parameters
    ----------
    **read_csv_kwargs
        Optional keyword arguments forwarded verbatim to ``pd.read_csv``
        (e.g., ``sep=';'``, ``encoding='latin-1'``).

    Examples
    --------
    >>> ingestor = CSVDataIngestor(sep=",", low_memory=False)
    >>> df = ingestor.ingest("data/house_prices.csv")
    """

    def __init__(self, **read_csv_kwargs: object) -> None:
        self._read_csv_kwargs = read_csv_kwargs

    def ingest(self, file_path: str) -> pd.DataFrame:
        """
        Read a CSV file from disk into a DataFrame.

        Parameters
        ----------
        file_path : str
            Path to the ``.csv`` file.

        Returns
        -------
        pd.DataFrame
            Loaded dataset.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist.
        pd.errors.ParserError
            If the file is not valid CSV.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: '{file_path}'")

        df: pd.DataFrame = pd.read_csv(file_path, **self._read_csv_kwargs)
        logger.info(
            "CSVDataIngestor: loaded '%s'  shape=%s  columns=%d",
            file_path,
            df.shape,
            len(df.columns),
        )
        return df


class ZipDataIngestor(DataIngestor):
    """
    Ingestor for ``.zip`` archives that contain one or more CSV files.

    By default the *first* CSV found inside the archive is loaded.  If the
    archive contains multiple CSVs, pass ``csv_index`` to select a specific
    one by its zero-based position in the archive name list.

    Parameters
    ----------
    csv_index : int, optional
        Zero-based index of the CSV to load when the archive holds multiple
        files.  Defaults to ``0`` (the first CSV found).
    **read_csv_kwargs
        Optional keyword arguments forwarded to ``pd.read_csv``.

    Examples
    --------
    >>> ingestor = ZipDataIngestor(csv_index=0)
    >>> df = ingestor.ingest("data/house_prices.zip")
    """

    def __init__(self, csv_index: int = 0, **read_csv_kwargs: object) -> None:
        self._csv_index = csv_index
        self._read_csv_kwargs = read_csv_kwargs

    def ingest(self, file_path: str) -> pd.DataFrame:
        """
        Extract the target CSV from a ZIP archive and load it.

        The archive is opened in read mode, the list of contained files is
        filtered to ``.csv`` extensions, and the file at ``csv_index`` is
        streamed directly into ``pd.read_csv`` without writing a temp file.

        Parameters
        ----------
        file_path : str
            Path to the ``.zip`` archive.

        Returns
        -------
        pd.DataFrame
            Contents of the selected CSV.

        Raises
        ------
        FileNotFoundError
            If *file_path* does not exist.
        ValueError
            If the archive contains no CSV files, or ``csv_index`` is out of
            range.
        zipfile.BadZipFile
            If the file is not a valid ZIP archive.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ZIP file not found: '{file_path}'")

        with zipfile.ZipFile(file_path, "r") as archive:
            csv_members: list[str] = [
                name for name in archive.namelist() if name.lower().endswith(".csv")
            ]

            if not csv_members:
                raise ValueError(
                    f"No CSV files found inside archive '{file_path}'. "
                    f"Contents: {archive.namelist()}"
                )

            if self._csv_index >= len(csv_members):
                raise ValueError(
                    f"csv_index={self._csv_index} is out of range. "
                    f"Archive contains {len(csv_members)} CSV file(s): {csv_members}"
                )

            if len(csv_members) > 1:
                logger.warning(
                    "ZipDataIngestor: archive '%s' contains %d CSVs — "
                    "loading index %d: '%s'. "
                    "Pass csv_index= to select a different file.",
                    file_path,
                    len(csv_members),
                    self._csv_index,
                    csv_members[self._csv_index],
                )

            target: str = csv_members[self._csv_index]
            with archive.open(target) as csv_file:
                df: pd.DataFrame = pd.read_csv(csv_file, **self._read_csv_kwargs)

        logger.info(
            "ZipDataIngestor: loaded '%s' → '%s'  shape=%s",
            file_path,
            target,
            df.shape,
        )
        return df


# ── Factory ────────────────────────────────────────────────────────────────


class DataIngestorFactory:
    """
    Central factory that maps file extensions to ``DataIngestor`` subclasses.

    Design decisions
    ----------------
    * **Registry-based routing** — the extension-to-class map lives in a
      class-level dict, making it trivially extensible via
      :meth:`register_ingestor` without touching existing code.
    * **Lazy instantiation** — the factory stores *classes*, not instances,
      so caller-supplied constructor kwargs are applied at the point of
      creation.
    * **Explicit error messages** — unsupported extensions raise immediately
      with the full list of registered handlers so operators know exactly
      what formats are available.

    Examples
    --------
    Register a custom Parquet ingestor at runtime::

        class ParquetDataIngestor(DataIngestor):
            def ingest(self, file_path: str) -> pd.DataFrame:
                return pd.read_parquet(file_path)

        DataIngestorFactory.register_ingestor(".parquet", ParquetDataIngestor)

    Then use it transparently::

        ingestor = DataIngestorFactory.get_ingestor("data/features.parquet")
        df = ingestor.ingest("data/features.parquet")
    """

    # Maps lowercase extension → concrete DataIngestor subclass.
    _registry: ClassVar[dict[str, type[DataIngestor]]] = {
        ".csv": CSVDataIngestor,
        ".zip": ZipDataIngestor,
    }

    @classmethod
    def get_ingestor(cls, file_path: str) -> DataIngestor:
        """
        Inspect *file_path*'s extension and return the correct ingestor.

        The factory performs *no* I/O itself — it only routes.  The returned
        object is a freshly instantiated concrete ``DataIngestor`` ready to
        call ``.ingest(file_path)`` on.

        Parameters
        ----------
        file_path : str
            Path whose extension determines the ingestor type.

        Returns
        -------
        DataIngestor
            Concrete ingestor matched to the file extension.

        Raises
        ------
        ValueError
            If the extension is not registered in the factory.

        Examples
        --------
        >>> ingestor = DataIngestorFactory.get_ingestor("data/train.csv")
        >>> df = ingestor.ingest("data/train.csv")
        """
        _, raw_ext = os.path.splitext(file_path)
        ext: str = raw_ext.lower()

        ingestor_cls: type[DataIngestor] | None = cls._registry.get(ext)
        if ingestor_cls is None:
            supported: list[str] = sorted(cls._registry.keys())
            raise ValueError(
                f"Unsupported file extension '{ext}' for path '{file_path}'. "
                f"Registered extensions: {supported}"
            )

        logger.debug(
            "DataIngestorFactory: extension='%s' → %s",
            ext,
            ingestor_cls.__name__,
        )
        return ingestor_cls()

    @classmethod
    def register_ingestor(
        cls,
        extension: str,
        ingestor_cls: type[DataIngestor],
    ) -> None:
        """
        Register a new ingestor class for the given file extension.

        Calling this with an already-registered extension *replaces* the
        existing mapping, enabling hot-patching in tests.

        Parameters
        ----------
        extension : str
            File extension including the leading dot (e.g., ``".parquet"``).
            Case is normalised to lowercase automatically.
        ingestor_cls : type[DataIngestor]
            A concrete subclass of ``DataIngestor`` to associate with
            *extension*.

        Raises
        ------
        TypeError
            If *ingestor_cls* is not a subclass of ``DataIngestor``.

        Examples
        --------
        >>> DataIngestorFactory.register_ingestor(".parquet", ParquetDataIngestor)
        """
        if not (isinstance(ingestor_cls, type) and issubclass(ingestor_cls, DataIngestor)):
            raise TypeError(
                f"ingestor_cls must be a subclass of DataIngestor, got {ingestor_cls!r}"
            )

        normalised_ext: str = extension.lower()
        if not normalised_ext.startswith("."):
            normalised_ext = f".{normalised_ext}"

        cls._registry[normalised_ext] = ingestor_cls
        logger.info(
            "DataIngestorFactory: registered '%s' → %s",
            normalised_ext,
            ingestor_cls.__name__,
        )

    @classmethod
    def list_supported_extensions(cls) -> list[str]:
        """
        Return a sorted list of all currently registered file extensions.

        Returns
        -------
        list[str]
            E.g. ``['.csv', '.zip']``.
        """
        return sorted(cls._registry.keys())
