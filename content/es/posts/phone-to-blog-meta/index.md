---
title: "Cómo Lancé un Blog Bilingüe Desde Mi Celular a las 2 AM Usando un Agente de IA"
date: 2026-05-21
draft: false
tags: ["Blog", "Hugo", "GitHub Pages", "AI Agents", "Meta"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "Sin laptop. Sin terminal. Solo un celular, Telegram, y un agente de IA que hizo push a GitHub mientras yo estaba en la cama."
ShowToc: true
ShowBreadCrumbs: true
---

Esta noche lancé este blog.

No desde mi laptop. No desde una terminal. Desde mi celular. A las 2 AM. Acostado en la cama.

Así fue exactamente como pasó, porque el workflow dice más sobre los agentes de IA que cualquier benchmark.

## El Setup

He estado guardando mis notas, ideas y borradores en un vault privado de Obsidian por meses. Algunos de esos borradores merecían ser públicos — pero moverlos de un vault privado a un blog público se sentía como fricción para la que no tenía tiempo.

Así que le pedí a mi agente de IA, Dae, que se encargara.

## El Stack

- **Hugo** — generador de sitios estáticos, rápido y nativo en markdown
- **PaperMod** — tema limpio, bilingüe, con modo oscuro
- **GitHub Actions** — construye y despliega en cada push
- **GitHub Pages** — hosting gratuito, sin servidores que administrar

## El Flujo

1. Le dije a Dae: "Crea un blog Hugo en un repo público de GitHub."
2. Dae construyó toda la estructura — config, tema, posts, workflow de GitHub Actions, todo — en el sandbox.
3. El primer approach de tema falló (módulos Hugo no cargaron). El segundo también (git submodules). El tercero funcionó: vendorizar los archivos del tema directamente.
4. La versión de Hugo era incorrecta (0.145.0 vs 0.146.0 mínimo para PaperMod). Dae lo detectó.
5. Cada fix fue un solo commit. Cada commit fue un solo push — desde el sandbox, vía HTTPS, autenticado por token.
6. GitHub Actions construyó y desplegó. El blog salió en vivo.

Nunca abrí una terminal en mi laptop. Ni siquiera toqué mi computadora.

## Lo Que Esto Demuestra Realmente

Esto no es sobre un blog. Es sobre lo que cambia cuando tienes un agente de IA persistente con acceso a tus archivos y capacidad de ejecutar.

Dae no solo generó texto. Hizo:
- Diagnosticar por qué el tema no cargaba
- Cambiar de módulos Hugo a archivos vendorizados
- Encontrar el mismatch de versión de Hugo en theme.toml
- Corregir y redesplegar — todo por Telegram

Eso no es un chatbot. Es un operador.

## La Historia Real

El blog tomó unos 30 minutos de idea a vivo. Hace un mes, esto habría sido un proyecto de fin de semana que nunca empezaba.

La diferencia no es habilidad. Es leverage.

Mi agente corre 24/7 en una Dell OptiPlex reciclada en mi casa. Cuesta casi nada. Y esta noche me ayudó a lanzar algo real mientras yo estaba medio dormido.

**Este es el post sobre cómo lancé el blog. ¿Suficientemente meta para ti?**
