import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import socket
import requests
from tqdm.auto import tqdm

def load_domains(filename):
    """Загрузка доменов из файла с обработкой кодировок"""
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'cp866']
    for enc in encodings:
        try:
            with open(filename, 'r', encoding=enc) as f:
                return {line.strip().lower() for line in f if line.strip()}
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Не удалось прочитать файл {filename}")

def check_domain_availability(domain):
    """Проверка доступности домена"""
    result = {'domain': domain, 'dns': None, 'http': None}

    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname(domain)
        result['dns'] = True
    except socket.gaierror:
        result['dns'] = False

    if result['dns']:
        for protocol in ['https', 'http']:
            try:
                response = requests.head(
                    f"{protocol}://{domain}",
                    timeout=5,
                    allow_redirects=True,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                result['http'] = response.status_code < 400
                break
            except requests.exceptions.RequestException:
                continue

    return result

def process_domains(main_file, whitelist_file, output_file, max_workers=10, batch_size=5000):
    """Основная функция обработки"""
    try:
        print("Загрузка доменов...")
        main_domains = load_domains(main_file)
        whitelist = load_domains(whitelist_file)

        # Находим пересечение доменов
        domains_to_check = main_domains & whitelist
        print(f"[ПРОВЕРКА] Найдено {len(domains_to_check)} совпадений с вайт-листом")

        if not domains_to_check:
            print("Нет доменов для проверки")
            return

        # Конвертируем в список для сохранения порядка
        domains_list = list(domains_to_check)

        # Разбиваем на пакеты
        batches = [domains_list[i:i + batch_size]
                   for i in range(0, len(domains_list), batch_size)]

        start_time = time.time()
        processed = 0

        # Создаем CSV файл
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['domain', 'dns', 'http']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for batch in tqdm(batches, desc="Обработка"):
                    try:
                        results = list(executor.map(check_domain_availability, batch))
                        processed += len(results)

                        # Записываем результаты в CSV
                        for result in results:
                            writer.writerow(result)

                        print(f"\rОбработано: {processed}/{len(domains_list)}", end="")
                    except Exception as e:
                        print(f"\nОшибка в пакете: {e}")
                        continue

        print(f"\nЗавершено. Результаты сохранены в {output_file}")
        print(f"Общее время: {time.time() - start_time:.2f} секунд")

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Проверка доменов по вайт-листу")
    parser.add_argument("main_file", help="Основной файл с доменами")
    parser.add_argument("whitelist", help="Файл вайт-листа")
    parser.add_argument("-o", "--output", required=True, help="Файл для результатов (CSV)")
    parser.add_argument("-w", "--workers", type=int, default=10, help="Количество потоков")
    parser.add_argument("-b", "--batch", type=int, default=5000, help="Размер пакета")

    args = parser.parse_args()

    process_domains(
        args.main_file,
        args.whitelist,
        args.output,
        args.workers,
        args.batch
    )