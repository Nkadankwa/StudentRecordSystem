from django.db import models

# Create your models here.
class Student(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    gender = models.CharField(max_length=100)
    age = models.IntegerField()

    def __str__(self):
        return self.name

