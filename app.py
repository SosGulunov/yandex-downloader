import os
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import requests
from io import BytesIO
from typing import Any, Dict, Optional

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)

# API Endpoints
YANDEX_DISK_API_BASE = "https://cloud-api.yandex.net/v1/disk/public/resources"
YANDEX_DISK_DOWNLOAD_URL = "https://cloud-api.yandex.net/v1/disk/public/resources/download"


def get_public_resources(public_key: str, path: str = "") -> Optional[Dict[str, Any]]:
    """
    Получает метаданные публичных ресурсов с Яндекс.Диска.

    :param public_key: Публичный ключ (URL) ресурса.
    :param path: Путь к нужному каталогу.
    :return: Словарь с данными или None в случае ошибки.
    """
    params = {
        "public_key": public_key,
        "path": path,
        "limit": 1000,  # Максимальное количество элементов
        "offset": 0,
    }
    try:
        response = requests.get(YANDEX_DISK_API_BASE, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении ресурсов: {e}")
        if response is not None:
            print(f"Ответ сервера: {response.text}")
        return None


def get_download_href(public_key: str, path: str) -> Optional[str]:
    """
    Получает ссылку для скачивания файла.

    :param public_key: Публичный ключ (URL) ресурса.
    :param path: Путь к файлу.
    :return: Ссылка для скачивания или None в случае ошибки.
    """
    params = {
        "public_key": public_key,
        "path": path,
    }
    try:
        response = requests.get(YANDEX_DISK_DOWNLOAD_URL, params=params)
        response.raise_for_status()
        data = response.json()
        href = data.get('href')
        if not href:
            print(f"'href' не найден в ответе: {data}")
        return href
    except requests.RequestException as e:
        print(f"Ошибка при получении ссылки для скачивания: {e}")
        if response is not None:
            print(f"Ответ сервера: {response.text}")
        return None


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Главная страница приложения. Позволяет пользователю ввести публичную ссылку.
    """
    if request.method == 'POST':
        public_link = request.form.get('public_link')
        if not public_link:
            flash("Пожалуйста, введите публичную ссылку.", "danger")
            return redirect(url_for('index'))
        return redirect(url_for('files', public_key=public_link))
    return render_template('index.html')


@app.route('/files')
def files():
    """
    Страница отображения списка файлов и папок по публичной ссылке.
    """
    public_key = request.args.get('public_key')
    path = request.args.get('path', "")  # Добавлено для поддержки папок
    filter_type = request.args.get('filter', "")

    if not public_key:
        flash("Отсутствует публичная ссылка.", "danger")
        return redirect(url_for('index'))

    resources = get_public_resources(public_key, path)
    if not resources:
        flash("Не удалось получить данные с Яндекс.Диска. Проверьте ссылку.", "danger")
        return redirect(url_for('index'))

    items = resources.get('_embedded', {}).get('items', [])

    # Фильтрация (опционально, если вы реализовали опциональные задачи)
    if filter_type == 'folder':
        items = [item for item in items if item.get('type') == 'dir']
    elif filter_type == 'document':
        doc_types = ['doc', 'docx', 'pdf', 'txt', 'xls', 'xlsx', 'ppt', 'pptx']
        items = [item for item in items if
                 item.get('type') == 'file' and item.get('file', {}).get('extension') in doc_types]
    elif filter_type == 'image':
        img_types = ['jpg', 'jpeg', 'png', 'gif', 'bmp']
        items = [item for item in items if
                 item.get('type') == 'file' and item.get('file', {}).get('extension') in img_types]

    return render_template('files.html', items=items, public_key=public_key, path=path)


@app.route('/download')
def download():
    """
    Обрабатывает скачивание выбранного файла.
    """
    public_key = request.args.get('public_key')
    path = request.args.get('path')
    name = request.args.get('name')

    if not all([public_key, path, name]):
        flash("Некорректные параметры для скачивания.", "danger")
        return redirect(url_for('files', public_key=public_key))

    href = get_download_href(public_key, path)
    if not href:
        flash("Не удалось получить ссылку для скачивания.", "danger")
        return redirect(url_for('files', public_key=public_key))

    try:
        file_response = requests.get(href)
        file_response.raise_for_status()
        return send_file(BytesIO(file_response.content), download_name=name, as_attachment=True)
    except requests.RequestException as e:
        flash(f"Ошибка при скачивании файла: {e}", "danger")
        return redirect(url_for('files', public_key=public_key))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(debug=True)