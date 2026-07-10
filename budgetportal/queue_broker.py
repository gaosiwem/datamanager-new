from django.utils import timezone

from django_q.brokers.orm import ORM, _timeout
from django_q.conf import Conf


class SqlServerSafeORMBroker(ORM):
    def dequeue(self):
        tasks = self.get_connection().filter(
            key=self.list_key,
            lock__lt=_timeout(),
        )[0:Conf.BULK]
        if tasks:
            task_list = []
            for task in tasks:
                # SQL Server can round datetime precision differently between the
                # initial SELECT and the follow-up UPDATE, so matching on the exact
                # previous lock value is unreliable. Re-checking eligibility keeps
                # the claim atomic enough for a single-row update without relying
                # on exact timestamp equality.
                claimed = self.get_connection().filter(
                    id=task.id,
                    key=self.list_key,
                    lock__lt=_timeout(),
                ).update(lock=timezone.now())
                if claimed:
                    task_list.append((task.pk, task.payload))
            return task_list
        return super().dequeue()
