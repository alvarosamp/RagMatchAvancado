'''
Conceito : Multi-tenancy

Multi-tenant = um unico sistema que serve MULTIPLAS empresas ao mesmo tempo,
de forma completamente isolada. Cada empresa é um `tenant``

Analogia : Um predio comercial .
    - O predio = nossa API
    - Cada escritorio = um tenant (empresa)
    - Cada funcionário = um usuario daquele tenant
    - Cada escritorio tem sua propria chave - nao tem acesso vizinho

No banco de dados, isolamente é feito pelo id_tenant:
    - Edital.tenant_id = 'empresa_abc' -> so a empresa abc pode acessar seus editais
    - QUando a empresa_abc faz login, o JWT carrega o tenant_id 'empresa_abc' -> todas as rotas usam esse tenant_id para filtrar os dados
    - Cada query filtra automaticamente pelo tenant_id

Vocabulário:
- Tenant: A empresa cliente que usa o sistema. Ex: "Empresa ABC"
- User: Um usuário que pertence a um tenant. Ex: "João da Empresa ABC"
- JWT (JSON Web Token): O token de autenticação que carrega informações do usuário e do tenant
- Claims: As informações codificadas dentro do JWT, como user_id e tenant_id
- Rbac (Role-Based Access Control): Controle de acesso baseado em funções, onde cada usuário tem uma função (ex: admin, user) que define o que pode acessar
'''

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

#Importante a mesma base do models.py princiapl para metadados
# Outra coisa importante : Todos os modelos deve usar a mesma instancia de base
# para o create_all() criar todas tabelas de uma vez
from app.db.models import Base

#Tenant - a empresa/organizacao
class Tenant(Base):
    '''
    Representa uma empresa que usa o sistema

    Cade tenant tem seus proprios editais, requisitos e resultados.
    Nenhum tenant exerga dados de outro tenant

    Campos:
    - id: ID unico do tenant
    - slug : identificador legível (ex: "empresa-abc")
    - name : nome completo da empresa
    - created_at: timestamp de criação
    - is_active: se o tenant está ativo (pode ser usado para soft delete)
    '''
    table_name = 'tenants'
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)  # ex: "empresa-abc
    name = Column(String, nullable=False)  # ex: "Empresa ABC LTDA"
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)

    #Um tenant tem multos usuarios
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    def __repr__(self):
        return f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"

#User - um usuario que pertence a um tenant
class User(Base):
    '''
    Representa um usuário que pertence a um tenant

    Campos:
    - id: ID unico do usuario
    - tenant_id: ID do tenant ao qual o usuario pertence
    - username: nome de usuario (ex: "joao.silva")
    - email: email do usuario
    - hashed_password: senha hasheada (nunca armazenar senha em texto puro)
    - is_active: se o usuario está ativo (pode ser usado para soft delete)
    '''
    __tablename__ = 'users'
id = Column(Integer, primary_key=True, index=True)
email = Column(String, unique=True, index=True)  # ex: "
hashed_password = Column(String, nullable=False)  # ex: "$2b$12$abc123..."
is_active = Column(Boolean, default=True)
role = Column(String, default="editor")  # ex: "admin" ou "user"
tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
created_at = Column(DateTime, server_default=func.now())

#Cada usuario pertence a um tenant
tenant = relationship("Tenant", back_populates="users")
def __repr__(self):
    return f"<User(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"


