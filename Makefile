DB_BACKUP_PATH=/tmp/$(shell date +'%Y%m%d_%H%M%S').dump
DB_BACKUP_ARCHIVE=${DB_BACKUP_PATH}.zip

.PHONY: backup
backup:
	@pg_dump --data-only -d "$$DATABASE_URL" > "${DB_BACKUP_PATH}" &>/dev/null
	@zip "${DB_BACKUP_ARCHIVE}" "${DB_BACKUP_PATH}" &>/dev/null
	@rm "${DB_BACKUP_PATH}"
	@echo "${DB_BACKUP_ARCHIVE}"

.PHONY: load
load:
	@./manage.py update_popular_tags &> /tmp/update_popular_tags.err
	@notify-send "Update tags OK"
