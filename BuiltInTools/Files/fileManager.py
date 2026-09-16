# from smolagents import tool
from pathlib import Path
from langchain_core.tools import tool
# directory_not_found
# not_a_file
# invalid_path
# write_failed
# unknown_operation

class FileManager:
    def __init__(self):
        self.ERRORS = {
            FileNotFoundError: {
                "type": "path_not_found",
                "suggestion": "Use find when the file location is unknown, or list when you know the directory."
            },
            PermissionError: {
                "type": "permission_denied",
                "suggestion": "Check whether the path is accessible."
            },
            IsADirectoryError: {
                "type": "is_a_directory",
                "suggestion": "Use list to inspect the directory contents."
            },
            NotADirectoryError: {
                "type": "not_a_directory",
                "suggestion": "Use list to inspect the directory structure."
            },
            UnicodeDecodeError: {
                "type": "decode_error",
                "suggestion": "The file may be binary or use a different text encoding."
            },
            OSError: {
                "type": "os_error",
                "suggestion": "Check the path and try again."
            }
        }
        self.IGNORED_DIRS = {
            ".git",
            ".venv",
            "venv",
            "env",
            "__pycache__",
            "node_modules",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "dist",
            "build",
        }
        self.MAX_FIND_RESULTS = 20

    def _getError(self, exception):
        for errorType, errorInfo in self.ERRORS.items():
            if(isinstance(exception, errorType)):
                return {
                    "type": errorInfo["type"],
                    "message": str(exception),
                    "suggestion": errorInfo["suggestion"]
                }
        return {
            "type": "unknown_error",
            "message": str(exception),
            "suggestion": "Check the path and try again."
        }

    def findFileRecursive(self, root: Path, query: str, results: list):
        if len(results) >= self.MAX_FIND_RESULTS:
            return
        try:
            items = root.iterdir()
        except PermissionError:
            return
        for item in items:
            if item.is_symlink():
                continue
            if item.is_dir():
                if item.name in self.IGNORED_DIRS:
                    continue
                self.findFileRecursive(item, query, results)
                if len(results) >= self.MAX_FIND_RESULTS:
                    return
            elif item.is_file() and query.lower() in item.name.lower():
                results.append({
                    "name": item.name,
                    "path": item.resolve().as_posix(),
                    "type": "file"
                })

    def findFiles(self, root: Path, query: str):
        try:
            root = Path(root)
            if not root.exists():
                raise FileNotFoundError(root)
            if not root.is_dir():
                raise NotADirectoryError(root)
            results = []
            self.findFileRecursive(root, query, results)
            return {
                "success": True,
                "path": root.resolve().as_posix(),
                "result": {
                    "query": query,
                    "results": results,
                    "count": len(results),
                    "limit_reached": len(results) >= self.MAX_FIND_RESULTS
                }
            }
        except Exception as e:
            return {
                "success": False,
                "path": root.resolve().as_posix(),
                "error": self._getError(e)
            }
    def listFiles(self, path):
        try:
            files = Path(path).iterdir()
            result = [
                {
                    "name": file.name,
                    "path": file.resolve().as_posix(),
                    "type": (
                        "file"
                        if file.is_file()
                        else "directory"
                        if file.is_dir()
                        else "other"
                    )
                }
                for file in files
            ]
            return {
                "success": True,
                "path": path,
                "result": result,
                "count": len(result)
            }
        except Exception as e:
            error = self._getError(e)
            return {
                "success": False,
                "path": path,
                "error": error
            }
    def readFile(self, path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                result = file.read()
            return {
                "success": True,
                "path": path,
                "result": result
            }
        except Exception as e:
            error = self._getError(e)
            return {
                "success": False,
                "path": path,
                "error": error
            }
    def overwriteFile(self, path, content):
        try:
            filePath = Path(path)
            filePath.parent.mkdir(parents=True, exist_ok=True)

            with filePath.open("w", encoding="utf-8") as file:
                file.write(content)

            result = "File written successfully."
            success = True
            return {
                "success": success,
                "path": path,
                "result": result
            }
        except Exception as e:
            error = self._getError(e)
            return {
                "success": False,
                "path": path,
                "error": error
            }
    def createDirectory(self, path):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            result = "Directory created successfully."
            return {
                "success": True,
                "path": path,
                "result": result
            }
        except Exception as e:
            error = self._getError(e)
            return {
                "success": False,
                "path": path,
                "error": error
            }
    def moveFile(self, sourcePath, destinationPath):
        try:
            source = Path(sourcePath)
            destination = Path(destinationPath)
            if not source.exists():
                raise FileNotFoundError(sourcePath)
            if destination.exists():
                raise FileExistsError(destinationPath)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
            result = "File moved successfully."
            return {
                "success": True,
                "path": sourcePath,
                "result": result
            }
        except Exception as e:
            error = self._getError(e)
            print("Error moving file:", error)
            return {
                "success": False,
                "path": sourcePath,
                "error": error
            }

fileManager = FileManager()

@tool
def listFiles(path: str) -> dict:
    """List files and directories in the specified path.
    Args:
        path (str): The path to list files and directories in.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.listFiles(path)

@tool
def readFile(path: str) -> dict:
    """Read the contents of a file.
    Args:
        path (str): The path to the file to read.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.readFile(path)

@tool
def overwriteFile(path: str, content: str) -> dict:
    """Overwrite a file with the specified content.
    Args:
        path (str): The path to the file to overwrite.
        content (str): The content to write to the file.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.overwriteFile(path, content)
@tool
def findFiles(root: str, query: str) -> dict:
    """Find files matching the query in the specified root directory.
    Args:
        root (str): The root directory to search in.
        query (str): The filename to search for.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.findFiles(root, query)

@tool 
def createDirectory(path: str) -> dict:
    """Create a new directory at the specified path.
    Args:
        path (str): The path to create the new directory.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.createDirectory(path)

@tool
def moveFile(sourcePath: str, destinationPath: str) -> dict:
    """Move a file from the source path to the destination path.
    Args:
        sourcePath (str): The path to the file to move.
        destinationPath (str): The path to move the file to.
    Returns:
        dict: A dictionary containing the results of the operation.
    """
    return fileManager.moveFile(sourcePath, destinationPath)

# print(fileManager.findFiles("C:", "borra", []))

if __name__ == "__main__":
    print(fileManager.findFiles("../../", "efirma"))