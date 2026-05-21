---
title: "La Arquitectura Que Necesitas Entender Antes de Tocar una Terminal"
date: 2026-05-21
draft: false
tags: ["AI Agents", "Arquitectura", "Self-Hosting", "OpenShell", "Principiantes"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "Nadie me explicó las capas claramente, así que las explico yo. Host, WSL, Docker, sandbox, gateway — esto es lo que corre dónde."
ShowToc: true
ShowBreadCrumbs: true
---

Nadie me explicó esto claramente, así que lo explico yo. Hay tres capas, y confundirlas te costará horas.

## Las Tres Capas

- **OpenShell** — el sandbox. Piensa en él como un contenedor Linux bloqueado donde tu agente de IA realmente corre. Tiene su propio sistema de archivos, sus propias reglas de red, y no confía en nada por defecto.
- **NemoClaw** — la distribución de NVIDIA del framework de agentes. Viene con inferencia optimizada para GPU y una API key de NVIDIA para pruebas. ¿Esa key? Es solo para *pruebas*. No recibes una advertencia cuando deja de funcionar.
- **OpenClaw** — el gateway que conecta tu sandbox a plataformas de chat (Telegram, Discord, etc.), programa cron jobs y gestiona el ciclo de vida del agente.

Si estás en Windows como yo, agrega otra capa: **WSL → Docker → OpenShell sandbox**. Cuatro capas de profundidad. Un error en cualquier capa rompe todo.

## Políticas de Red: El Asesino Silencioso

El sandbox bloquea todo el tráfico saliente por defecto. Necesitas permitir *explícitamente* cada endpoint de API que tu agente vaya a llamar.

Esto es buena seguridad — pero también es la razón #1 por la que mi agente se quedó ahí sin hacer nada por horas mientras yo debuggeaba.

No entendía la sintaxis de las políticas. Metí la pata con la indentación en archivos YAML. YAML no perdona errores de indentación. Un espacio de más y tu política falla silenciosamente.

## Reconstruir el Sandbox Borra Todo

Esta dolió. Modificas una configuración del sandbox, reconstruyes, y todo tu trabajo dentro del sandbox desaparece. Cada script, cada credencial, cada archivo de configuración.

Aprendes a externalizar todo rápido — o aprendes por las malas.

**Lección clave:** Mantén tu trabajo fuera del sandbox. El sandbox es desechable por diseño.

## Lo Que Me Diría a Mí Mismo en la Instalación #1

1. Dibuja la arquitectura en papel primero. En serio.
2. Guarda cada API key que generes. No puedo enfatizar esto lo suficiente.
3. Prueba las políticas de red un endpoint a la vez.
4. La indentación no es opcional en YAML. Usa un linter.
5. Asume que reconstruirás el sandbox al menos una vez. Planifícalo.
