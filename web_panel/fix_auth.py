# -*- coding: utf-8 -*-
import sys

with open('app/templates/simulation.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    "headers: { 'Content-Type': 'application/json' },",
    "headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + localStorage.getItem('token') },"
)

text = text.replace(
    "fetch('/api/simulation/stop', { method: 'POST' })",
    "fetch('/api/simulation/stop', { method: 'POST', headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })"
)

text = text.replace(
    "fetch('/api/simulation/status')",
    "fetch('/api/simulation/status', { headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') } })"
)

with open('app/templates/simulation.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Auth Headers Fixed')
