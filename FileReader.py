from pathlib import Path
from typing import List, Tuple


class FileReader:
    main_dir: Path

    def __init__(self, data_dir: str) -> None:

        path = Path(data_dir)
        if not path.is_dir():
            raise FileNotFoundError(f"The required directory does not exist: '{path}'")

        self.main_dir = path

    def get_fnames_and_dir(self, verbose=False) -> List[Tuple[str, str]]:
        """Returns a list of (file names, file location)

        Returns:
            List[Tuple[str, str]]: A list of tuples containing file names and their corresponding file locations.
        """

        files = []
        for path in self.main_dir.rglob("*"):
            if path.is_file():
                file_name = path.stem
                file_addr = path.resolve()
                files.append((file_name, file_addr))
                if verbose:
                    print(f"File found: {file_name}")

        return files
