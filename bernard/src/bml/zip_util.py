import zipfile
import os


def extract_zip_ignore_root(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Get all paths in the archive
        all_names = zip_ref.namelist()

        # Find all root-level entries
        root_dirs = set()
        for name in all_names:
            parts = name.strip("/").split("/")
            if parts:
                root_dirs.add(parts[0])

        # Decide if there's only one root directory and no files at the root
        is_single_root = len(root_dirs) == 1
        has_file_at_root = any("/" not in name.rstrip("/") for name in all_names)

        if is_single_root and not has_file_at_root:
            # Get the single top-level folder name
            root_prefix = next(iter(root_dirs)) + '/'
            for member in all_names:
                if member.startswith(root_prefix):
                    # Strip the root folder
                    relative_path = member[len(root_prefix):]
                    if relative_path:  # skip empty names
                        target_path = os.path.join(extract_to, relative_path)
                        if member.endswith('/'):
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as out_file:
                                out_file.write(zip_ref.read(member))
        else:
            # Extract normally
            zip_ref.extractall(path=extract_to)

# Example usage:
# extract_zip_ignore_root("archive.zip", "output_folder")


def extract_zip_ignore_single_root(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        all_names = zip_ref.namelist()

        # Get only file paths (not directories)
        file_names = [name for name in all_names if not name.endswith('/')]

        # Extract the root folder part of each file path
        top_level_folders = set()
        files_in_root = False

        for name in file_names:
            parts = name.split('/')
            if len(parts) == 1:
                # This file is in the root of the zip
                files_in_root = True
                break
            top_level_folders.add(parts[0])

        if not files_in_root and len(top_level_folders) == 1:
            # Strip the single top-level directory
            root_prefix = next(iter(top_level_folders)) + '/'
            for member in all_names:
                if member.startswith(root_prefix):
                    relative_path = member[len(root_prefix):]
                    if not relative_path:
                        continue  # Skip the top-level dir entry itself
                    target_path = os.path.join(extract_to, relative_path)
                    if member.endswith('/'):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as f:
                            f.write(zip_ref.read(member))
        else:
            # Extract everything normally
            zip_ref.extractall(path=extract_to)


def create_zip_from_directory(source_dir, zip_path):
    # Ensure absolute paths
    source_dir = os.path.abspath(source_dir)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(source_dir):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                # Store the file with a relative path inside the ZIP
                arcname = os.path.relpath(file_path, start=source_dir)
                zipf.write(file_path, arcname)
