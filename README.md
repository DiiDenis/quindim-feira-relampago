# Feira Relâmpago

Projeto da avaliação técnica do Clube Quindim para reserva de estoque e pedidos.

O backend expõe a API Flask na porta 8000 e usa MongoDB 8 standalone. Nesta etapa, o frontend ainda não faz parte do ambiente.

## Executar e testar o backend

Crie `.env` a partir de `.env.example` e execute:

```bash
docker compose up -d --build
docker compose run --rm testes
```

O primeiro comando sobe MongoDB e API. O segundo executa os testes unitários e de integração; o serviço `testes` não permanece em execução. A saúde da API fica disponível em `http://localhost:8000/healthz`.
