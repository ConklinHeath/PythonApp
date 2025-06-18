def write_file_add(file_to_modify, text):
    with open(file_to_modify, 'r') as file:
        content = file.read()
        new_content = content + str(text) + '\n'
    with (open(file_to_modify, 'w') as file):
        file.write(new_content)


def write_file_line(file_to_modify, text, line_number):
    with open(file_to_modify, 'r') as file:
        lines = file.readlines()
    if 0 < line_number <= len(lines):
        lines[line_number - 1] = str(text) + '\n'
        with open(file_to_modify, 'w') as file:
            file.writelines(lines)


def read_file(file_to_read):
    with open(file_to_read, 'r') as file:
        content = file.read()
    return content


def read_file_line(file_to_read, line_number):
    with open(file_to_read, 'r') as file:
        for _ in range(line_number - 1):
            file.readline()
        line = file.readline().strip()
        return line


def count_lines_in_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return sum(1 for _ in file)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return 0
    except Exception as e:
        print(f"An error occurred: {e}")
        return 0

