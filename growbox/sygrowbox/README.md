- **Адаптер** - реализует интерфейс для записи/чтения из гроубокса
- **Эмулятор** - это **адаптер**, в котором реализован (эмулирован) гроубокс. Реализация гроубокса подразумевает парсинг G-кода и его выполнение
- **Построитель G-кода** - реализует интерфейс для взаимодействия с гроубоксом через набор методов, функционально аналогичных G-коду. Методы генерируют G-код и отправляют в гроубокс через **адаптер**, через **адаптер** считывается ответ.

- Гроубокс - это реальное устройство. Оно принимает команды от клиента и передаёт обновления (только изменившиеся показания датчиков) на клиентов. Гроубокс может быть только один.
- Клиент - это приложение, реализующее интерфейс для управления гроубоксом. Отдаёт команды в гроубокс, передаёт обновления (только изменение настроек) другим клиентам (если команда выполнена успешно), получает обновления (показания датчиков, изменения настроек) от других клиентов. Клиентов может быть множество.

Клиентом может являться:
- веб-интерфейс веб-сайта производителя,
- графический интерфейс настольного, мобильного или носимого устройства,
- связь с гроубоксом через последовательный порт
- панель управления на гроубоксе
- веб-интерфейс внутри гроубокса