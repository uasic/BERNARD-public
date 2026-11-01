"""
Various file utilities.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""

import bml.conn as con

import os
import shutil
import pathlib
import glob


kilo = 1024
mega = kilo * 1024
giga = mega * 1024
tera = giga * 1024


def human_readable_file_size(size_bytes: int):
    """Convert size in bytes into a human-readable string."""
    if size_bytes >= tera:
        return str(int((float(size_bytes) / tera) + .5)) + ' TB'

    if size_bytes >= giga:
        return str(int((float(size_bytes) / giga) + .5)) + ' GB'

    if size_bytes >= mega:
        return str(int((float(size_bytes) / mega) + .5)) + ' MB'

    if size_bytes >= kilo:
        return str(int((float(size_bytes) / kilo) + .5)) + ' KB'

    return str(size_bytes) + ' B'


def extract_common_root(path1: str, path2: str):
    """Find common beginning of two paths."""
    seek = 0
    common_end = None

    while True:
        idx1 = path1.find('/', seek)
        if idx1 < 0:
            break

        idx2 = path2.find('/', seek)
        if idx2 < 0:
            break

        if idx1 != idx2:
            break

        if path1[:idx1 + 1] == path2[:idx2 + 1]:
            common_end = idx1 + 1
            seek = idx1 + 1

    if common_end is None:
        return '', path1, path2

    return path1[:common_end], path1[common_end:], path2[common_end:]


def split(path: str):
    """Split file name into directory, name and extension."""
    dir_part, file_part = os.path.split(path)
    base_name, extension = os.path.splitext(file_part)

    result = {}
    result['dir'] = dir_part
    result['name'] = base_name
    result['ext'] = extension

    return result


def split_path(path: str):
    """Split file name only into directory and the rest."""
    dir_part, file_part = os.path.split(path)

    result = {}
    result['dir'] = dir_part
    result['name'] = file_part

    return result


def deep_split(path: str, outer_ext: list = None, replace_dot: str = None):
    """Split file name into directory, name and extension.

    outer_ext can be a string or a list of strings, which
    enumerate outermost extension, like .gz, .zip, ...
    to be considered an additional extension.
    WARNING: leading dot must be included, e.g. ['.gz', '.zip']
    If the last extension is one of outer_ext, then this and
    the next extension is joined into a commond extension;
    otherwise only the last extension (the part from the last dot
    to the end) is considered as an extension.

    In the rest of basename (after stripping of one or two
    extensions) appearances of dots can be replaced by a string
    replace_dot.
    """
    if (outer_ext is not None) and isinstance(outer_ext, str):
        temp = []
        temp.append(outer_ext)
        outer_ext = temp

    dir_part, file_part = os.path.split(path)
    base_name, extension = os.path.splitext(file_part)

    result = {}
    result['dir'] = dir_part

    if (outer_ext is not None) and (extension in outer_ext):
        base_name, ext2 = os.path.splitext(base_name)
        extension = ext2 + extension

    if replace_dot is not None:
        base_name = base_name.replace('.', replace_dot)

    result['name'] = base_name
    result['ext'] = extension

    return result


def basename(path: str):
    """Strip directory and all extensions from path."""
    while True:
        fsplit = split(path)
        if fsplit['ext'] == '':
            break

        path = fsplit['name']

    return fsplit['name']


def file_w_top_dir(file: str):
    """Trim file to contain only file name and the topmost directory.

    This is meant to reduce length of on screen rendered file names.
    """
    parts = split(file)
    dirs = parts['dir'].split('/')

    if len(dirs) == 1:
        result = dirs[-1]
    elif len(dirs) > 1:
        result = '.../' + dirs[-1]
    else:
        result = ''

    return result + '/' + parts['name'] + parts['ext']


def file_exists(file: str):
    """Return True if file exists, False otherwise."""
    return os.path.isfile(file)


def dir_exists(dir_name: str):
    """Return True if directory exists, False otherwise."""
    return os.path.isdir(dir_name)


def assure_file_abort(file: str):
    """Abort, if file does not exit."""
    if file is None:
        return

    if not os.path.isfile(file):
        con.abort('File\n' + file + '\n     does not exist!')


def assure_file_throw(file: str):
    """Throw, if file does not exit."""
    if file is None:
        return

    if not os.path.isfile(file):
        raise IOError


def assure_file_bool(file: str):
    """Return False, if file does not exit."""
    if file is None:
        return True

    return os.path.isfile(file)


def assure_readable_abort(file: str):
    """Abort, if file does not exit or cannot be open for reading."""
    if file is None:
        return

    assure_file_abort(file)

    try:
        with open(file, 'r') as _:
            pass
    except Exception as Ex:
        con.abort('File ' + file + ' cannot be opened for reading ' + '(' + str(Ex) + ').')


def assure_readable_throw(file: str):
    """Throw, if file does not exit or cannot be open for reading."""
    if file is None:
        return

    assure_file_throw(file)

    try:
        with open(file, 'r') as _:
            pass
    except Exception as Ex:
        raise IOError(str(Ex))


def assure_readable_bool(file: str):
    """Return False, if file does not exit or cannot be open for reading."""
    if file is None:
        return True

    if not assure_file_bool(file):
        return False

    try:
        with open(file, 'r') as _:
            return True
    except Exception:
        pass
    return False


def assure_nonempty_abort(file: str):
    """Abort, if file does not exit, cannot be open for reading or is empty."""
    if file is None:
        return

    assure_readable_abort(file)

    if os.path.getsize(file) == 0:
        con.abort('File ' + file + ' exists but is empty!')


def assure_nonempty_throw(file: str):
    """Throw, if file does not exit, cannot be open for reading or is empty."""
    if file is None:
        return

    assure_readable_throw(file)

    if os.path.getsize(file) == 0:
        raise IOError


def assure_nonempty_bool(file: str):
    """Return False, if file does not exit, cannot be open for reading or is empty."""
    if file is None:
        return True

    if not assure_readable_bool(file):
        return False

    return os.path.getsize(file) > 0


def assure_dir_abort(dir_name: str):
    """Abort, if dir does not exit."""
    if dir_name is None:
        return

    if not os.path.isdir(dir_name):
        con.abort('Directory\n' + dir_name + '\n     does not exist!')


def assure_dir_throw(dir_name: str):
    """Throw, if dir does not exit."""
    if dir_name is None:
        return

    if not os.path.isdir(dir_name):
        raise IOError


def assure_dir_bool(dir_name: str):
    """Return False, if dir does not exit."""
    if dir_name is None:
        return True

    return os.path.isdir(dir_name)


def create_dir(dir_name: str, exist_ok=False):
    """Create directory or abort."""
    if dir_name is None:
        return

    try:
        os.makedirs(dir_name, exist_ok=exist_ok)
    except Exception as Ex:
        con.abort('Directory ' + dir_name + ' cannot be created ' + '(' + str(Ex) + ').')


def create_dir_exist_ok(dir_name: str):
    """Create directory; return silently, if dir already exists."""
    if dir_name is None:
        return True

    try:
        os.makedirs(dir_name, exist_ok=True)
        return True
    except Exception:
        pass

    return False


def recreate_dir(dir_name: str):
    """Delete and then creates directory in order to assure that it is empty."""
    if dir_name is None:
        return

    try:
        shutil.rmtree(dir_name)
    except Exception:
        pass

    create_dir(dir_name)


def remove_dir(dir_name: str):
    """Delete directory."""
    if dir_name is None:
        return

    try:
        shutil.rmtree(dir_name)
    except Exception:
        pass


def move_subdir_to_dir(abs_src_subdir: str, dst_dir: str,
                       exists_ok: bool=False, throw: bool=False, abort: bool=True):
    """Move first level subdir to dst_dir and preserve its name."""
    try:
        src_split = split(abs_src_subdir)
        if len(src_split['ext']) > 0:
            if throw:
                raise IOError

            if abort:
                con.abort('move_subdir_to_dir: abs_src_subdir is a file not a directory.')

            return False

        shutil.move(abs_src_subdir, dst_dir)
    except Exception as Ex:
        if throw:
            raise

        if abort:
            con.abort('Cannot move subdir ' + abs_src_subdir + ' to dir ' + dst_dir + ' (' + str(Ex) + ').')

        return False

    return dst_dir + '/' + src_split['name']


def change_directory(dir_name: str):
    """Change the current dir."""
    if dir_name is None:
        return

    try:
        os.chdir(dir_name)
    except Exception as Ex:
        con.abort('Cannot change to directory ' + dir_name + ' (' + str(Ex) + ').')


def copy(src: str, dst: str, exists_ok: bool = False):
    """Copy file."""
    if exists_ok:
        if os.path.islink(dst):
            try:
                os.unlink(dst)
            except Exception as Ex:
                con.abort('FILES copy: the existing symbolic link (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

        if os.path.isfile(dst):
            try:
                os.remove(dst)
            except Exception as Ex:
                con.abort('FILES copy: the existing file (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

    try:
        if os.path.isfile(src):
            shutil.copyfile(src, dst)
        elif os.path.isdir(src):
            shutil.copytree(src, dst)
    except Exception as Ex:
        if not exists_ok:
            con.abort('Cannot copy file ' + src + ' to ' + dst + ' (' + str(Ex) + ').')


def copy_to_dir(src: str, dst_directory: str, dst_name_prepend: str = '', exists_ok: bool = False):
    """Copy file to dst_directory and preserve its base name."""
    try:
        src_basename = os.path.basename(src)
        dst = dst_directory + '/' + dst_name_prepend + src_basename
        copy(src, dst, exists_ok)
    except Exception as Ex:
        if not exists_ok:
            con.abort('Cannot copy file ' + src + ' to directory ' + dst_directory + ' (' + str(Ex) + ').')

    return dst


def copy_list_to_dir(src_list: list, dst_directory: str, dst_name_prepend: str = '', exists_ok: bool = False):
    """Copy list of files to dst_directory and preserve its base name."""
    result = []

    for src in src_list:
        try:
            src_basename = os.path.basename(src)
            dst = dst_directory + '/' + dst_name_prepend + src_basename
            copy(src, dst, exists_ok)
            result.append(dst)
        except Exception as Ex:
            if not exists_ok:
                con.abort('Cannot copy file ' + src + ' to directory ' + dst_directory + ' (' + str(Ex) + ').')

    return result


def copy_all_in_dir(src_dir: str, dst_dir: str):
    """Copy all files from src_dir to dst_dir."""
    items = list_in_dir(src_dir)

    for item in items:
        copy(src_dir + '/' + item, dst_dir + '/' + item)


def copy_directory_tree(src_dir: str, dst_dir: str):
    """Recursively copy entire src directory structure. dst_dir must not exist."""
    return shutil.copytree(src_dir, dst_dir, symlinks=False)


def copy_with_metadata(src: str, dst: str, exists_ok: bool = False):
    """Copy file and metadata."""
    try:
        shutil.copy2(src, dst)
    except Exception as Ex:
        if not exists_ok:
            con.abort('Cannot copy file with metadata ' + src + ' to ' + dst + ' (' + str(Ex) + ').')


def copy_with_metadata_to_dir(src: str, dst_directory: str, dst_name_prepend: str = '', exists_ok: bool = False):
    """Copy file to dst_directory and preserve its base name and metadata."""
    try:
        src_basename = os.path.basename(src)
        dst = dst_directory + '/' + dst_name_prepend + src_basename
        copy_with_metadata(src, dst, exists_ok)
    except Exception as Ex:
        if not exists_ok:
            con.abort('Cannot copy file with metadata ' + src + ' to directory ' + dst_directory + ' (' + str(Ex) + ').')

    return dst


def copy_with_metadata_all_in_dir(src_dir: str, dst_dir: str):
    """Copy all files and their metadata from src_dir to dst_dir."""
    items = list_in_dir(src_dir)

    for item in items:
        copy_with_metadata(src_dir + '/' + item, dst_dir + '/' + item)


def move(src: str, dst: str, exists_ok: bool = False):
    """Move file."""
    if exists_ok:
        if os.path.islink(dst):
            try:
                os.unlink(dst)
            except Exception as Ex:
                con.abort('FILES move: the existing symbolic link (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

        if os.path.isfile(dst):
            try:
                os.remove(dst)
            except Exception as Ex:
                con.abort('FILES move: the existing file (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

    try:
        shutil.move(src, dst)
    except Exception as Ex:
        con.abort('Cannot move file ' + src + ' to ' + dst + ' (' + str(Ex) + ').')


def move_to_dir(src: str, dst_directory: str, dst_name_prepend: str = '', exists_ok: bool = False):
    """Move file to dst_directory and preserve its base name."""
    try:
        src_basename = os.path.basename(src)
        dst = dst_directory + '/' + dst_name_prepend + src_basename
        move(src, dst, exists_ok)
    except Exception as Ex:
        if not exists_ok:
            con.abort('Cannot move file ' + src + ' to directory ' + dst_directory + ' (' + str(Ex) + ').')

    return dst


def move_in_dir(src_dir: str, dst_dir: str):
    """Move all files from src_dir to dst_dir."""
    items = list_in_dir(src_dir)

    for item in items:
        move(src_dir + '/' + item, dst_dir + '/' + item)


def move_all_in_dir(src_dir: str, dst_dir: str):
    """Move all files and subdirs from src_dir to dst_dir."""
    items = list_all_in_dir(src_dir)

    for item in items:
        move(src_dir + '/' + item, dst_dir + '/' + item)


def delete(file: str, does_not_exist_ok=False):
    """Delete file."""
    if file is None:
        return

    try:
        os.remove(file)
    except Exception as Ex:
        if(does_not_exist_ok):
            return
        con.abort('Delete file failed: ' + file + ' (' + str(Ex) + ').')


def delete_target_file_and_symlink(file: str, does_not_exist_ok=False):
    """Delete file. If symlink, follow it to its origin, delete true file, then delete symlink as well"""
    if file is None:
        return

    try:
        if not os.path.islink(file):
            delete(file, does_not_exist_ok)
        return

        target = os.path.realpath(file)
    except Exception as Ex:
        if(does_not_exist_ok):
            return
        con.abort('Delete file failed: ' + file + ' (' + str(Ex) + ').')

    delete(target, does_not_exist_ok)
    delete(file, does_not_exist_ok)


def delete_files(directory: str, filePattern: str):
    """Delete files with global pattern from parent dir."""
    for file in pathlib.Path(directory).glob(filePattern):
        if os.path.isfile(file):
            file.unlink()


def delete_directory(directory: str, does_not_succeed_ok=False):
    """Delete empty directory."""
    if directory is None:
        return

    try:
        os.rmdir(directory)
    except Exception as Ex:
        if(does_not_succeed_ok):
            return
        con.abort('Remove directory failed: ' + directory + ' (' + str(Ex) + ').')


def delete_directory_tree(directory: str, does_not_succeed_ok=False):
    """Delete directory and its contents."""
    if directory is None:
        return

    try:
        shutil.rmtree(directory)
    except Exception as Ex:
        if(does_not_succeed_ok):
            return
        con.abort('Remove directory and its contents failed: ' + directory + ' (' + str(Ex) + ').')


def delete_generic(entry: str, does_not_succeed_ok=False):
    """Delete file or directory and its contents."""
    if entry is None:
        return

    if os.path.isfile(entry):
        delete(entry, does_not_succeed_ok)
    else:
        delete_directory_tree(entry, does_not_succeed_ok)


def delete_1st_subDirs(parent_directory: str, subDirPattern: str):
    """Delete subdirs with global pattern from parent dir."""
    for dir_name in pathlib.Path(parent_directory).glob(subDirPattern):
        shutil.rmtree(dir_name)


def list_1st_subDirs(parent_directory: str):
    """Return list of 1st level subdirs in a parent dir."""
    return next(os.walk(parent_directory))[1]


def list_sub_dirs_in_dir(directory: str, dirPattern: str = None, full_path: bool = False):
    """List only subdirs in dir. If dirPattern is not None, list only subdirs that match it."""
    if dirPattern is None:
        if full_path:
            items = os.listdir(directory)

            result = []

            for item in items:
                full = os.path.join(directory, item)
                if not os.path.isdir(full):
                    continue

                result.append(full)

            return result
        else:
            return [f for f in os.listdir(directory) if os.path.isdir(os.path.join(directory, f))]

    items = glob.glob(directory + '/' + dirPattern)
    result = []

    for item in items:
        if not os.path.isdir(item):
            continue

        if full_path:
            result.append(item)
        else:
            isplit = split(item)
            result.append(isplit['name'] + isplit['ext'])

    return result


def list_in_dir(directory: str, filePattern: str = None, full_path: bool = False):
    """List only files in dir. If filePattern is not None, list only files that match it."""
    if filePattern is None:
        if full_path:
            items = os.listdir(directory)

            result = []

            for item in items:
                full = os.path.join(directory, item)
                if not os.path.isfile(full):
                    continue

                result.append(full)

            return result
        else:
            return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]

    items = glob.glob(directory + '/' + filePattern)
    result = []

    for item in items:
        if not os.path.isfile(item):
            continue

        if full_path:
            result.append(item)
        else:
            isplit = split(item)
            result.append(isplit['name'] + isplit['ext'])

    return result


def list_all_in_dir(directory: str, filePattern: str = None, full_path: bool = False):
    """List files and subdirs in dir. If filePattern is not None, list only entries that match it."""
    if filePattern is None:
        if full_path:
            items = os.listdir(directory)

            result = []

            for item in items:
                result.append(directory + '/' + item)

            return result
        else:
            return os.listdir(directory)

    items = glob.glob(directory + '/' + filePattern)
    result = []

    for item in items:
        if full_path:
            result.append(item)
        else:
            isplit = split(item)
            result.append(isplit['name'] + isplit['ext'])

    return result


def create_symlink(src: str, dst: str, exist_ok=False):
    """Create symlink."""
    if exist_ok:
        if os.path.islink(dst):
            try:
                os.unlink(dst)
            except Exception as Ex:
                con.abort('FILES create_symlink: the existing symbolic link (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

        if os.path.isfile(dst):
            try:
                os.remove(dst)
            except Exception as Ex:
                con.abort('FILES create_symlink: the existing file (' + src + ' => ' + dst + ') cannot be deleted ' + '(' + str(Ex) + ').')

    try:
        if os.path.islink(src):
            src = os.path.realpath(src)

        os.symlink(src, dst)
    except Exception as Ex:
        con.abort('The specified symbolic link (' + src + ' => ' + dst + ') cannot be created ' + '(' + str(Ex) + ').')


def create_symlink_in_dir(src: str, dst_directory: str, dst_name_prepend: str = '', exist_ok=False):
    """Create symlink within dst_directory. It adopts source file name."""
    src_basename = os.path.basename(src)
    dst = dst_directory + '/' + dst_name_prepend + src_basename
    create_symlink(src, dst, exist_ok)
    return dst


def create_symlinks_in_dir(src_list: list, dst_directory: str, dst_name_prepend: str = '', exist_ok=False):
    """Create symlinks of files on a list within dst_directory. It adopts source file name."""
    results = []
    for src in src_list:
        src_basename = os.path.basename(src)
        dst = dst_directory + '/' + dst_name_prepend + src_basename
        create_symlink(src, dst, exist_ok)
        results.append(dst)
    return results


def delete_symlink(src: str, does_not_exis_ok=True):
    """Delete symlink."""
    try:
        os.unlink(src)
    except Exception as Ex:
        if does_not_exis_ok:
            return
        con.abort('Symbolic link (' + src + ') cannot be deleted ' + '(' + str(Ex) + ').')


def follow_link(src: str):
    """Finds target file in case scr is a symbolic link or several of them."""
    return os.path.realpath(src)


def generic_delete(obj):
    """Delete filesystem entry with a method that is appropriate for the entry type."""
    if obj is None:
        return

    if os.path.exists(obj):
        if os.path.isdir(obj):
            if os.path.islink(obj):
                os.unlink(obj)
            else:
                shutil.rmtree(obj)
        else:
            if os.path.islink(obj):
                os.unlink(obj)
            else:
                os.remove(obj)


def read_line_from_file(file: str, zero_line_idx: int):
    """Read specific line from a file, strip white spaces. Return None if line or file does not exist."""
    try:
        with open(file, 'r') as src:
            for idx, line in enumerate(src):
                if idx == zero_line_idx:
                    return line.strip()
    except Exception:
        return None

    return None


def read_lines_from_file(file: str, zero_line_idx: list):
    """Read specific lines from a file, strip white spaces. Return None if file does not exist."""
    try:
        result = []

        with open(file, 'r') as src:
            for idx, line in enumerate(src):
                if idx in zero_line_idx:
                    result.append(line.strip())

            return result
    except Exception:
        return None

    return None


def read_all_lines_from_file(file: str, strip: bool = False):
    """Read all lines from a file. Return None if line or file does not exist."""
    try:
        result = []

        with open(file, 'r') as src:
            for line in src:
                if strip:
                    lstrip = line.strip()
                    if len(lstrip) > 0:
                        result.append(lstrip)
                else:
                    result.append(line)

        return result
    except Exception:
        return None

    return None


def read_lines_that_begin_with(file: str, begin_str: str, strip: bool = False):
    """Read only lines that begin with begin_str. Return None if line or file does not exist."""
    try:
        result = []

        with open(file, 'r') as src:
            for line in src:
                if strip:
                    lstrip = line.strip()
                else:
                    lstrip = line

                if lstrip.startswith(begin_str):
                    result.append(lstrip)

        return result
    except Exception:
        return None

    return None
