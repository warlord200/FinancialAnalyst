from pathlib import Path


class FileReader:
    main_dir: Path

    def __init__(self, data_dir: str) -> None:

        path = Path(data_dir)
        if not path.is_dir():
            raise FileNotFoundError(f"The required directory does not exist: '{path}'")

        self.main_dir = path

    def get_fnames_and_dir(
        self, verbose=False, inclu_file=True
    ) -> list[tuple[str, str]]:
        """Returns a list fnames and its location

        Args:
            verbose (bool, optional): For debugging. Defaults to False.
            inclu_file (bool, optional): False to exclude file itself when returning path. Defaults to True. (True: ./dir/file.txt, False: ./dir)

        Returns:
            List[Tuple[str, str]]: A list of tuples containing the file name and its corresponding directory path.
        """

        files = []
        for path in self.main_dir.rglob("*"):
            if path.is_file():
                file_name = path.stem

                if not inclu_file:
                    file_addr = path.parent.resolve()
                else:
                    file_addr = path.resolve()
                files.append((file_name, file_addr))
                if verbose:
                    print(f"File found: {file_name}")
                    print(f"File path: {file_addr}")

        return files

    def get_storage_location(
        self,
        new_file: str = "",
        storage_dir: str = "./storage",
        verbose=False,
        valid_extensions: list[str] = [".pdf"],
    ) -> list[tuple[str, str]]:
        """Build storage paths for source files that match allowed extensions.

        For each matching file under ``self.main_dir``, this method creates a
        directory at ``{storage_dir}/{parent_folder}_{file_stem}`` (if it does not
        already exist).

        Args:
            new_file (str, optional): If provided, append this filename inside each
                generated storage directory and return that file path. If empty,
                return the storage directory path itself.
            storage_dir (str, optional): Base directory where generated storage
                directories are created. Defaults to ``"./storage"``.
            verbose (bool, optional): Print discovered source file names and their
                mapped storage paths. Defaults to False.
            valid_extensions (List[str], optional): File extensions to include when
                scanning ``self.main_dir``. Defaults to ``[".pdf"]``.

        Returns:
            List[Tuple[str, str]]: Tuples of ``(source_file_stem, storage_path)`` for
            each matching source file.
        """
        files = []
        new_storage_dir = Path(storage_dir)
        for path in self.main_dir.rglob("*"):
            if path.is_file() and path.suffix in valid_extensions:
                file_name = path.stem
                file_parent = path.parent.name
                new_path = new_storage_dir / (file_parent + "_" + file_name)

                new_path.mkdir(parents=True, exist_ok=True)

                if new_file != "":
                    file_addr = new_path / new_file
                else:
                    file_addr = new_path.resolve()

                files.append((file_name, file_addr))
                if verbose:
                    print(f"File found: {file_name}")
                    print(f"File path: {file_addr}")

        return files
