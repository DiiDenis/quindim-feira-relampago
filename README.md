# Feira Relâmpago

Projeto da avaliação técnica do Clube Quindim para reserva de estoque e pedidos.

O projeto usa Flask na API, MongoDB 8 standalone e Nuxt no frontend.

## Executar e testar o backend

Crie `.env` a partir de `.env.example` e execute:

```bash
docker compose up -d --build
docker compose run --rm testes
docker compose --profile navegador run --rm testes-navegador
```

O primeiro comando sobe MongoDB, API e frontend. O segundo executa os testes unitários e de integração do backend. O terceiro executa separadamente os testes de navegador no Chromium; os serviços de teste não permanecem em execução.

- Frontend: `http://localhost:3000`
- Saúde da API: `http://localhost:8000/healthz`
