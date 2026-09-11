///*******************************************************************************
// * COPYRIGHT NOTICE *
// * 
// * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org Contributors : -
// * 
// * This file is part of ProjeQtOr.
// * 
// * ProjeQtOr is free software: you can redistribute it and/or modify it under
// * the terms of the GNU Affero General Public License as published by the Free Software
// * Foundation, either version 3 of the License, or (at your option) any later
// * version.
// * 
// * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
// * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
// * A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.
// * 
// * You should have received a copy of the GNU Affero General Public License along with
// * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
// * 
// * You can get complete code of ProjeQtOr, other resource, help and information
// * about contributors at http://www.projeqtor.org
// * 
// * DO NOT REMOVE THIS NOTICE **
// ******************************************************************************/
//
//// ============================================================================
//// All specific ProjeQtOr functions and variables for Dialog Purpose
//// This file is included in the main.php page, to be reachable in every context
//// ============================================================================

//=============================================================================
//= Columns Layout
//=============================================================================

function onColumnHeaderClickedSort(ev) {
  const th=ev.currentTarget;
  const table=th.closest('table');
  const thIndex=Array.from(th.parentElement.children).indexOf(th);
  const ascending=!('sort' in th.dataset) || th.dataset.sort != 'asc';
  tableRowsSortByColumn(table,thIndex,ascending);

  const allTh=table.querySelectorAll(':scope > thead > tr > td');
  // for( var th2 of allTh ) {
  // delete th2.dataset['sort'];
  // }
  allTh.forEach(function(th2) {
    delete th2.dataset['sort']
    if (th2.classList.contains('sortable') && th2.textContent!=th.textContent) th2.innerHTML=th2.textContent;
  });

  th.dataset['sort']=ascending ? 'asc' : 'desc';
}

function tableRowsSortByColumn(table,columnIndex,ascending) {
  var th=Array.from(table.querySelectorAll('thead'));
  if (!th.length) {
    table.createTHead();
    th=Array.from(table.querySelectorAll('thead'));
    const
    tb=Array.from(table.querySelectorAll('tbody'));
    const
    tr=Array.from(table.querySelectorAll('tr'));
    th[0].insertAdjacentElement('afterbegin',tr[0]);
    tr.splice(0,1);
  }
  const col=Array.from(table.querySelectorAll(':scope > thead > tr'));
  const columnName=col[0].cells[columnIndex].textContent; // not use but keep this
  // variable, it can be
  // interested to have this
  // columb name if we wnt to
  // improve sort function
  var arrowFlip=(!ascending) ? 'background-position: -21px 0px;' : '';
  col[0].cells[columnIndex].innerHTML=columnName + '<span class="dijitInline dijitArrowNode" style="position: relative;float: right;top: 5px;right: 5px;' + arrowFlip + '"></span>';
  const rows=Array.from(table.querySelectorAll(':scope > tbody > tr'));
  // rows.sort( ( x, y ) => {
  rows.sort(function(x,y) {
    const xValue=x.cells[columnIndex].textContent;
    const yValue=y.cells[columnIndex].textContent;
    if (xValue.match("#[0-9]+") && yValue.match("#[0-9]+")) // if it's an id
    // (#XXXX format)
    {
      const xNum=parseFloat(xValue.replace(/\D+/g,''));
      const yNum=parseFloat(yValue.replace(/\D+/g,''));
      return ascending ? (xNum - yNum) : (yNum - xNum);
    }
    return ascending ? (('' + xValue).localeCompare(yValue)) : (('' + yValue).localeCompare(xValue));
  });
  // for( var row of rows ) {
  // table.tBodies[0].appendChild( row );
  // }
  rows.forEach(function(row) {
    table.tBodies[0].appendChild(row);
  });
}
