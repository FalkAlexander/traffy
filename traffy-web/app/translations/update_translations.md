pybabel extract -F babel.cfg -k _l -o strings.pot .
pybabel update -i strings.pot -d app/translations
pybabel compile -d app/translations
