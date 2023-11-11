--
-- PostgreSQL database dump
--

-- Dumped from database version 14.4 (Debian 14.4-1.pgdg110+1)
-- Dumped by pg_dump version 14.9

-- Started on 2023-11-08 18:29:07

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 3 (class 2615 OID 2200)
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- TOC entry 3353 (class 0 OID 0)
-- Dependencies: 3
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 216 (class 1259 OID 16427)
-- Name: music_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.music_links (
    id_musicas integer NOT NULL,
    name character varying(45) NOT NULL,
    url character varying(244) NOT NULL,
    user_id integer NOT NULL,
    title character varying(250)
);


--
-- TOC entry 215 (class 1259 OID 16426)
-- Name: music_links_id_musicas_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.music_links_id_musicas_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3354 (class 0 OID 0)
-- Dependencies: 215
-- Name: music_links_id_musicas_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.music_links_id_musicas_seq OWNED BY public.music_links.id_musicas;


--
-- TOC entry 214 (class 1259 OID 16399)
-- Name: niveis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.niveis (
    id_niveis integer NOT NULL,
    nome_nivel character varying(45) NOT NULL,
);


--
-- TOC entry 213 (class 1259 OID 16398)
-- Name: niveis_id_niveis_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.niveis_id_niveis_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3355 (class 0 OID 0)
-- Dependencies: 213
-- Name: niveis_id_niveis_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.niveis_id_niveis_seq OWNED BY public.niveis.id_niveis;


--
-- TOC entry 210 (class 1259 OID 16385)
-- Name: servidores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.servidores (
    id_servidores integer NOT NULL,
    nome_servidor character varying(45) NOT NULL,
    numero_id_servidor character varying(18) NOT NULL
);


--
-- TOC entry 209 (class 1259 OID 16384)
-- Name: servidores_id_servidores_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.servidores_id_servidores_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3356 (class 0 OID 0)
-- Dependencies: 209
-- Name: servidores_id_servidores_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.servidores_id_servidores_seq OWNED BY public.servidores.id_servidores;


--
-- TOC entry 212 (class 1259 OID 16392)
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id_usuarios integer NOT NULL,
    nome_usuario character varying(45) NOT NULL,
    user_id_discord character varying(45) NOT NULL,
    nivel_id integer NOT NULL,
    experiencia character varying(45) DEFAULT 0 NOT NULL,
    servidor_id integer DEFAULT 0 NOT NULL,
    youtube character varying(200),
    twitch character varying(200),
    twitter character varying(200),
    outros character varying(2000),
    total_mensagens integer DEFAULT 0
);


--
-- TOC entry 211 (class 1259 OID 16391)
-- Name: usuarios_id_usuarios_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_usuarios_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- TOC entry 3357 (class 0 OID 0)
-- Dependencies: 211
-- Name: usuarios_id_usuarios_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_usuarios_seq OWNED BY public.usuarios.id_usuarios;


--
-- TOC entry 3189 (class 2604 OID 16430)
-- Name: music_links id_musicas; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.music_links ALTER COLUMN id_musicas SET DEFAULT nextval('public.music_links_id_musicas_seq'::regclass);


--
-- TOC entry 3187 (class 2604 OID 16402)
-- Name: niveis id_niveis; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.niveis ALTER COLUMN id_niveis SET DEFAULT nextval('public.niveis_id_niveis_seq'::regclass);


--
-- TOC entry 3182 (class 2604 OID 16388)
-- Name: servidores id_servidores; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidores ALTER COLUMN id_servidores SET DEFAULT nextval('public.servidores_id_servidores_seq'::regclass);


--
-- TOC entry 3183 (class 2604 OID 16395)
-- Name: usuarios id_usuarios; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id_usuarios SET DEFAULT nextval('public.usuarios_id_usuarios_seq'::regclass);


--
-- TOC entry 3345 (class 0 OID 16399)
-- Dependencies: 214
-- Data for Name: niveis; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.niveis VALUES (1, 'Rookies');
INSERT INTO public.niveis VALUES (2, 'Rookies');
INSERT INTO public.niveis VALUES (3, 'Rookies');
INSERT INTO public.niveis VALUES (4, 'Rookies');
INSERT INTO public.niveis VALUES (5, 'Rookies');
INSERT INTO public.niveis VALUES (6, 'Adventurers');
INSERT INTO public.niveis VALUES (7, 'Adventurers');
INSERT INTO public.niveis VALUES (8, 'Adventurers');
INSERT INTO public.niveis VALUES (9, 'Adventurers');
INSERT INTO public.niveis VALUES (10, 'Adventurers');
INSERT INTO public.niveis VALUES (11, 'Veterans');
INSERT INTO public.niveis VALUES (12, 'Veterans');
INSERT INTO public.niveis VALUES (13, 'Veterans');
INSERT INTO public.niveis VALUES (14, 'Veterans');
INSERT INTO public.niveis VALUES (15, 'Veterans');
INSERT INTO public.niveis VALUES (16, 'Monarchs');
INSERT INTO public.niveis VALUES (17, 'Monarchs');
INSERT INTO public.niveis VALUES (18, 'Monarchs');
INSERT INTO public.niveis VALUES (19, 'Monarchs');
INSERT INTO public.niveis VALUES (20, 'Monarchs');
INSERT INTO public.niveis VALUES (21, 'Kings');
INSERT INTO public.niveis VALUES (22, 'Kings');
INSERT INTO public.niveis VALUES (23, 'Kings');
INSERT INTO public.niveis VALUES (24, 'Kings');
INSERT INTO public.niveis VALUES (25, 'Kings');
INSERT INTO public.niveis VALUES (26, 'Emperors');
INSERT INTO public.niveis VALUES (27, 'Emperors');
INSERT INTO public.niveis VALUES (28, 'Emperors');
INSERT INTO public.niveis VALUES (29, 'Emperors');
INSERT INTO public.niveis VALUES (30, 'Emperors');
INSERT INTO public.niveis VALUES (31, 'The Living Legends');
INSERT INTO public.niveis VALUES (32, 'The Living Legends');
INSERT INTO public.niveis VALUES (33, 'The Living Legends');
INSERT INTO public.niveis VALUES (34, 'The Living Legends');
INSERT INTO public.niveis VALUES (35, 'The Living Legends');
INSERT INTO public.niveis VALUES (36, 'The Ascended Ones');
INSERT INTO public.niveis VALUES (37, 'The Ascended Ones');
INSERT INTO public.niveis VALUES (38, 'The Ascended Ones');
INSERT INTO public.niveis VALUES (39, 'The Ascended Ones');
INSERT INTO public.niveis VALUES (40, 'The Ascended Ones');
INSERT INTO public.niveis VALUES (41, 'Lesser Gods');
INSERT INTO public.niveis VALUES (42, 'Lesser Gods');
INSERT INTO public.niveis VALUES (43, 'Lesser Gods');
INSERT INTO public.niveis VALUES (44, 'Lesser Gods');
INSERT INTO public.niveis VALUES (45, 'Lesser Gods');
INSERT INTO public.niveis VALUES (46, 'Greater Gods');
INSERT INTO public.niveis VALUES (47, 'Greater Gods');
INSERT INTO public.niveis VALUES (48, 'Greater Gods');
INSERT INTO public.niveis VALUES (49, 'Greater Gods');
INSERT INTO public.niveis VALUES (50, 'Greater Gods');
INSERT INTO public.niveis VALUES (51, 'Assembly of the Seven');
INSERT INTO public.niveis VALUES (52, 'God');


--
-- TOC entry 3358 (class 0 OID 0)
-- Dependencies: 215
-- Name: music_links_id_musicas_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.music_links_id_musicas_seq', 25, true);


--
-- TOC entry 3359 (class 0 OID 0)
-- Dependencies: 213
-- Name: niveis_id_niveis_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.niveis_id_niveis_seq', 31, true);


--
-- TOC entry 3360 (class 0 OID 0)
-- Dependencies: 209
-- Name: servidores_id_servidores_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.servidores_id_servidores_seq', 3, true);


--
-- TOC entry 3361 (class 0 OID 0)
-- Dependencies: 211
-- Name: usuarios_id_usuarios_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usuarios_id_usuarios_seq', 24, true);


--
-- TOC entry 3197 (class 2606 OID 16432)
-- Name: music_links music_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.music_links
    ADD CONSTRAINT music_links_pkey PRIMARY KEY (id_musicas);


--
-- TOC entry 3195 (class 2606 OID 16404)
-- Name: niveis niveis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.niveis
    ADD CONSTRAINT niveis_pkey PRIMARY KEY (id_niveis);


--
-- TOC entry 3191 (class 2606 OID 16390)
-- Name: servidores servidores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidores
    ADD CONSTRAINT servidores_pkey PRIMARY KEY (id_servidores);


--
-- TOC entry 3193 (class 2606 OID 16397)
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id_usuarios);


--
-- TOC entry 3199 (class 2606 OID 16412)
-- Name: usuarios fk_numero_id_servidor; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT fk_numero_id_servidor FOREIGN KEY (servidor_id) REFERENCES public.servidores(id_servidores);


--
-- TOC entry 3200 (class 2606 OID 16433)
-- Name: music_links fk_numero_id_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.music_links
    ADD CONSTRAINT fk_numero_id_usuario FOREIGN KEY (user_id) REFERENCES public.usuarios(id_usuarios);


--
-- TOC entry 3198 (class 2606 OID 16405)
-- Name: usuarios fk_usuarios_niveis; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT fk_usuarios_niveis FOREIGN KEY (nivel_id) REFERENCES public.niveis(id_niveis);


-- Completed on 2023-11-08 18:29:24

--
-- PostgreSQL database dump complete
--

