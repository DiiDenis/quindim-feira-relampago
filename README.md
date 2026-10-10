# Feira Relâmpago

Projeto da avaliação técnica do Clube Quindim para reserva de estoque e pedidos.

A aplicação será construída em etapas pequenas, com testes e revisão antes de cada commit. As instruções para executar e testar o projeto serão acrescentadas conforme a implementação avançar.

## Testes

Com `.env` criado a partir de `.env.example`, suba o ambiente e execute a suíte unitária e de integração:

```bash
docker compose up -d --build
docker compose run --rm testes
```

O serviço `testes` pertence ao profile de teste e não é iniciado por `docker compose up`.
