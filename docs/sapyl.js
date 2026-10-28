/* SAPyL: página do projeto.
   Só acrescenta recursos: sem JavaScript a página continua completa. */

/**
 * Mesma regra de `sapyl.palavras.preparar_termos` (testada em tests/test_site.py):
 * cada termo separado por vírgula vira uma expressão exata, com '+' no lugar
 * dos espaços, e os termos se juntam com '+'.
 * "lingua portuguesa, norma culta" -> "\"lingua+portuguesa\"+\"norma+culta\""
 */
function prepararTermo(linha) {
  return String(linha)
    .split(',')
    .map((termo) => termo.trim())
    .filter((termo) => termo !== '')
    .map((termo) => '"' + termo.split(/\s+/).join('+') + '"')
    .join('+');
}

/** Minutos para raspar `materias` matérias de uma casa, com o limite de 35 por minuto. */
function minutosParaRaspar(materias, porMinuto = 35) {
  const n = Math.max(0, Number(materias) || 0);
  return n / porMinuto;
}

function formatarDuracao(minutos) {
  if (minutos < 1) return 'menos de 1 minuto';
  const total = Math.round(minutos);
  const horas = Math.floor(total / 60);
  const resto = total % 60;
  if (horas === 0) return `cerca de ${total} minuto${total === 1 ? '' : 's'}`;
  const h = `${horas} hora${horas === 1 ? '' : 's'}`;
  return resto ? `cerca de ${h} e ${resto} min` : `cerca de ${h}`;
}

if (typeof module !== 'undefined') {
  // Para os testes (node)
  module.exports = { prepararTermo, minutosParaRaspar, formatarDuracao };
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    iniciarTema();
    iniciarCopiar();
    iniciarAbas();
    iniciarConsulta();
    iniciarTempo();
    iniciarPlenario();
    iniciarMenu();
  });
}

/* --- Tema claro/escuro --------------------------------------------------- */

function lerPreferencia() {
  try {
    return localStorage.getItem('sapyl-tema');
  } catch {
    return null;
  }
}

function gravarPreferencia(tema) {
  try {
    localStorage.setItem('sapyl-tema', tema);
  } catch {
    /* navegação privada: o tema vale só nesta visita */
  }
}

function iniciarTema() {
  const botao = document.querySelector('.tema');
  if (!botao) return;
  const raiz = document.documentElement;
  const sistemaEscuro = window.matchMedia('(prefers-color-scheme: dark)');
  const salvo = lerPreferencia();
  if (salvo === 'claro' || salvo === 'escuro') raiz.dataset.tema = salvo;

  const atual = () => raiz.dataset.tema || (sistemaEscuro.matches ? 'escuro' : 'claro');
  const rotular = () => {
    const proximo = atual() === 'escuro' ? 'claro' : 'escuro';
    botao.setAttribute('aria-label', `Mudar para o tema ${proximo}`);
    botao.title = `Tema ${proximo}`;
  };

  botao.hidden = false;
  rotular();
  botao.addEventListener('click', () => {
    const novo = atual() === 'escuro' ? 'claro' : 'escuro';
    raiz.dataset.tema = novo;
    gravarPreferencia(novo);
    rotular();
  });
  sistemaEscuro.addEventListener('change', rotular);
}

/* --- Copiar os comandos -------------------------------------------------- */

function iniciarCopiar() {
  const aviso = document.createElement('p');
  aviso.className = 'so-leitor';
  aviso.setAttribute('aria-live', 'polite');
  document.body.append(aviso);

  document.querySelectorAll('pre > code').forEach((codigo) => {
    const pre = codigo.parentElement;
    const bloco = document.createElement('div');
    bloco.className = 'bloco-codigo';
    pre.before(bloco);
    bloco.append(pre);

    const botao = document.createElement('button');
    botao.type = 'button';
    botao.className = 'copiar';
    botao.textContent = 'Copiar';
    botao.setAttribute('aria-label', 'Copiar os comandos');
    bloco.append(botao);

    botao.addEventListener('click', async () => {
      const texto = codigo.textContent;
      let ok = false;
      try {
        await navigator.clipboard.writeText(texto);
        ok = true;
      } catch {
        ok = copiarComSelecao(texto);
      }
      botao.textContent = ok ? 'Copiado!' : 'Selecione e copie';
      aviso.textContent = ok ? 'Comandos copiados.' : '';
      setTimeout(() => {
        botao.textContent = 'Copiar';
      }, 2000);
    });
  });
}

function copiarComSelecao(texto) {
  const area = document.createElement('textarea');
  area.value = texto;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.append(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

/* --- Abas de instalação -------------------------------------------------- */

function iniciarAbas() {
  document.querySelectorAll('[data-abas]').forEach((grupo) => {
    const lista = grupo.querySelector('[role="tablist"]');
    const abas = [...grupo.querySelectorAll('[role="tab"]')];
    if (!lista || abas.length === 0) return;

    const escolher = (aba, focar) => {
      abas.forEach((a) => {
        const ativa = a === aba;
        a.setAttribute('aria-selected', String(ativa));
        a.tabIndex = ativa ? 0 : -1;
        document.getElementById(a.getAttribute('aria-controls')).hidden = !ativa;
      });
      if (focar) aba.focus();
    };

    lista.hidden = false;
    grupo.classList.add('abas--ativas');
    const windows = /Windows/i.test(navigator.userAgent);
    escolher(windows ? abas[1] : abas[0], false);

    abas.forEach((aba, i) => {
      aba.addEventListener('click', () => escolher(aba, false));
      aba.addEventListener('keydown', (evento) => {
        const passo = { ArrowRight: 1, ArrowLeft: -1 }[evento.key];
        if (passo) {
          evento.preventDefault();
          escolher(abas[(i + passo + abas.length) % abas.length], true);
        }
      });
    });
  });
}

/* --- Ferramentas: palavra -> busca, tempo -------------------------------- */

function iniciarConsulta() {
  const caixa = document.querySelector('[data-consulta]');
  if (!caixa) return;
  const entrada = caixa.querySelector('input');
  const saida = caixa.querySelector('output');
  const atualizar = () => {
    // No arquivo CSV, a linha com vírgula vem entre aspas; aqui elas são opcionais
    const linha = entrada.value.trim().replace(/^"(.*)"$/, '$1');
    saida.textContent = prepararTermo(linha) || '(digite uma palavra)';
  };
  caixa.hidden = false;
  entrada.addEventListener('input', atualizar);
  atualizar();
}

function iniciarTempo() {
  const caixa = document.querySelector('[data-tempo]');
  if (!caixa) return;
  const entrada = caixa.querySelector('input');
  const saida = caixa.querySelector('output');
  const atualizar = () => {
    const minutos = minutosParaRaspar(entrada.value);
    saida.textContent = `${formatarDuracao(minutos)} (mais o tempo dos PDFs, se baixar)`;
  };
  caixa.hidden = false;
  entrada.addEventListener('input', atualizar);
  atualizar();
}

/* --- Plenário: as cadeiras acendem como casas visitadas ------------------ */

function iniciarPlenario() {
  const cadeiras = [...document.querySelectorAll('.plenario .cadeira')];
  if (cadeiras.length === 0) return;
  const calmo = window.matchMedia('(prefers-reduced-motion: reduce)');
  // Ordem de visita embaralhada, sempre a mesma
  const ordem = cadeiras
    .map((c, i) => ({ c, chave: (i * 37) % cadeiras.length }))
    .sort((a, b) => a.chave - b.chave)
    .map((item) => item.c);

  if (calmo.matches) {
    ordem.slice(0, Math.round(ordem.length * 0.6)).forEach((c) => c.classList.add('acesa'));
    return;
  }

  let i = 0;
  let relogio = null;
  const passo = () => {
    if (i > 0) ordem[i - 1].classList.replace('visitando', 'acesa');
    if (i === ordem.length) {
      relogio = setTimeout(() => {
        ordem.forEach((c) => c.classList.remove('acesa', 'visitando'));
        i = 0;
        passo();
      }, 2500);
      return;
    }
    ordem[i].classList.add('visitando');
    i += 1;
    relogio = setTimeout(passo, 140);
  };
  const parar = () => {
    clearTimeout(relogio);
    relogio = null;
  };

  // Só anima quando o desenho está na tela
  const observador = new IntersectionObserver(([item]) => {
    if (item.isIntersecting && relogio === null) passo();
    else if (!item.isIntersecting) parar();
  });
  observador.observe(document.querySelector('.plenario'));
}

/* --- Menu: marca a seção visível ----------------------------------------- */

function iniciarMenu() {
  const links = [...document.querySelectorAll('.menu a')];
  const secoes = links.map((a) => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const observador = new IntersectionObserver(
    (itens) => {
      itens.forEach((item) => {
        if (!item.isIntersecting) return;
        links.forEach((a) =>
          a.setAttribute('aria-current', String(a.getAttribute('href') === `#${item.target.id}`)),
        );
      });
    },
    { rootMargin: '-40% 0px -55% 0px' },
  );
  secoes.forEach((s) => observador.observe(s));
}
