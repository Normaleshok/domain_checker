import time
from concurrent.futures import ThreadPoolExecutor
import socket
import requests
from tqdm import tqdm  # Импорт библиотеки для прогресс-бара
import logging
logging.basicConfig(filename='check.log', level=logging.INFO, encoding='utf-8')

def process_domains(input_file, output_file=None, max_workers=10, batch_size=5000):
    """Обработка доменов пакетами"""
    def read_domains(filename):
        encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'cp866']
        for enc in encodings:
            try:
                with open(filename, 'r', encoding=enc) as file:
                    return [line.strip() for line in file if line.strip()]
            except UnicodeDecodeError:
                continue
        raise ValueError("Не удалось прочитать файл")

    try:
        all_domains = read_domains(input_file)
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return

    print(f"[ПРОВЕРКА] {len(all_domains)} ДОМЕНОВ...")

    start_time = time.time()
    processed = 0

    # Разбиваем на пакеты
    domain_batches = [all_domains[i:i + batch_size]
                      for i in range(0, len(all_domains), batch_size)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Используем tqdm для отображения прогресса
        for current_batch in tqdm(domain_batches, desc="Обработка доменов"):
            try:
                results = list(executor.map(check_domain_availability, current_batch))
                processed += len(results)

                if output_file:
                    with open(output_file, 'a', encoding='utf-8') as output_f:
                        for result in results:
                            output_f.write(f"{result['domain']},{result['dns']},{result['http']}\n")

                print(f"\rОбработано: {processed}/{len(all_domains)} | Время: {time.time() - start_time:.2f} сек", end="")

            except (socket.gaierror, requests.exceptions.RequestException) as e:
                print(f"\nОшибка в пакете: {e}")
                continue
            except KeyboardInterrupt as interrupt:
                print("\nПрерывание пользователем. Частичные результаты сохранены.")
                break

    print(f"\nЗавершено. Всего обработано {processed} доменов за {time.time() - start_time:.2f} секунд")

def check_domain_availability(domain):
    """Проверка доступности домена"""
    result = {'domain': domain, 'dns': None, 'http': None}

    # DNS проверка
    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname(domain)
        result['dns'] = True
    except socket.gaierror:
        result['dns'] = False

    # HTTP проверка только если DNS разрешился
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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Файл с доменами")
    parser.add_argument("-o", "--output", help="Файл для результатов")
    parser.add_argument("-w", "--workers", type=int, default=10, help="Количество потоков")
    parser.add_argument("-b", "--batch", type=int, default=5000, help="Размер пакета")

    args = parser.parse_args()
    process_domains(args.input_file, args.output, args.workers, args.batch)