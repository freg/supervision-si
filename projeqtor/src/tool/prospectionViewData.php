<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ============================================================================
 * Builds the whole prospection screen as one array. Emits nothing, so it can be
 * called outside a request.
 *
 * The cost is a fixed number of queries, whatever the number of prospects : one
 * per table, never one per row.
 */

/**
 * Turns a list of ids into an IN clause, guarding against injection and against
 * the empty list, which is not valid SQL.
 */
function prospectionViewInClause($ids) {
  $clean=array();
  foreach ($ids as $id) { $clean[intval($id)]=intval($id); }
  if (! count($clean)) return '(0)';
  return '(' . implode(',', $clean) . ')';
}

/**
 * Reads every list of values the screen displays, in one block. showIdle is on : a
 * value sent to the bin must still resolve, or old records show an empty cell.
 */
function prospectionViewLabels() {
  $labels=array();
  foreach (array('DomainProspect', 'ProspectionSource', 'ProspectQualification',
                 'Language', 'Engagement', 'Affectable', 'ProspectEventType',
                 'Client') as $class) {
    $labels[$class]=SqlList::getList($class, 'name', null, true);
  }
  // Engagements and statuses need their colour too, which SqlList does not carry.
  $labels['EngagementColor']=array();
  $q=Sql::query("SELECT id, color FROM engagement");
  while ($r=Sql::fetchLine($q)) { $labels['EngagementColor'][$r['id']]=$r['color']; }
  $labels['Status']=array();
  $q=Sql::query("SELECT id, name, color FROM status");
  while ($r=Sql::fetchLine($q)) {
    $labels['Status'][$r['id']]=array('name'=>$r['name'], 'color'=>$r['color']);
  }
  return $labels;
}

/**
 * Resolves an id against one of the loaded lists, or gives back an empty string.
 */
function prospectionViewName($labels, $class, $id) {
  if (! $id) return '';
  return isset($labels[$class][$id]) ? $labels[$class][$id] : '';
}

/**
 * Records what a responsible's thumbnail needs, a picture or an initial and the
 * name : the screen draws it, this only carries the data.
 *
 * Once per resource : reading the thumbnail hits the disk, and the same handful of
 * resources appears on hundreds of lines. Those carry the identifier only.
 */
function prospectionViewThumb($labels, $id, &$thumbs) {
  $id=intval($id);
  if (! $id) return 0;
  if (! isset($thumbs[$id])) {
    $file=Affectable::getThumbUrl('Affectable', $id, 32);
    $name=prospectionViewName($labels, 'Affectable', $id);
    $isFile=(pq_substr($file, 0, 6)!='letter');
    $thumbs[$id]=array(
      'isfile' => $isFile,
      'file'   => htmlEncode($isFile ? $file : pq_strtoupper(pq_mb_substr($name, 0, 1, 'UTF-8'))),
      'name'   => htmlEncode($name),
    );
  }
  return $id;
}

/**
 * Builds one line of the Informations block. A column the record has no field for
 * stays empty : a client has no email, a contact no engagement.
 */
function prospectionViewInfoLine($refType, $refId, $kind, $cells) {
  $line=array('refType'=>$refType, 'refId'=>intval($refId), 'kind'=>$kind,
              'company'=>'', 'contact'=>'', 'domain'=>'', 'source'=>'', 'email'=>'',
              'qualification'=>'', 'language'=>'', 'engagement'=>'',
              'engagementColor'=>'',
              'status'=>'', 'statusColor'=>'', 'responsible'=>'', 'idResponsible'=>0);
  foreach ($cells as $k=>$v) { $line[$k]=($v===null)?'':$v; }
  return $line;
}

/**
 * Builds one line of a financial sub block. One amount column only, taxed or not
 * according to the global parameter, never both.
 */
function prospectionViewMoneyLine($labels, $refType, $r, $dateField, $showFull) {
  $amount     =$showFull ? $r['fullAmount']      : $r['untaxedAmount'];
  $amountLocal=$showFull ? $r['fullAmountLocal'] : $r['untaxedAmountLocal'];
  return array(
    'refType'     => $refType,
    'refId'       => intval($r['id']),
    'name'        => (string)$r['name'],
    'date'        => htmlFormatDate($r[$dateField], true),
    'amount'      => htmlDisplayLocalCurrency($r['idProject'], $amount, $amountLocal),
    'status'      => isset($labels['Status'][$r['idStatus']]) ? $labels['Status'][$r['idStatus']]['name'] : '',
    'statusColor' => isset($labels['Status'][$r['idStatus']]) ? $labels['Status'][$r['idStatus']]['color'] : '',
  );
}

/**
 * Puts one action into the shape the Actions block expects. An action naming a
 * contact behaves as a contact line : blue, and opening that contact. idContact is
 * what ties an action to a contact, whichever record created it, so both the colour
 * and the target read from it.
 */
function prospectionViewEventLine($labels, $e, $toBeRecontacted) {
  $parentType=$e['refType'];
  $parentId=intval($e['refId']);
  if (intval($e['idContact'])) { $parentType='Contact'; $parentId=intval($e['idContact']); }
  $kind=($parentType=='Prospect') ? 'prospect' : (($parentType=='Contact') ? 'contact' : 'client');
  return array(
    'refType'         => 'ProspectEvent',
    'refId'           => intval($e['id']),
    // The screen opens the record that carries the action, not the action.
    'parentType'      => $parentType,
    'parentId'        => $parentId,
    'kind'            => $kind,
    'date'            => htmlFormatDate($e['eventDateTime'], true),
    'type'            => prospectionViewName($labels, 'ProspectEventType', $e['idProspectEventType']),
    'name'            => (string)$e['name'],
    'toBeRecontacted' => $toBeRecontacted,
  );
}

/**
 * Orders actions from the most recent. Two sources already sorted give an unsorted
 * merge, and a line gathers up to three.
 */
function prospectionViewSortEvents(&$events) {
  usort($events, function($a, $b) {
    if ($a['eventDateTime']==$b['eventDateTime']) return intval($b['id'])-intval($a['id']);
    return ($a['eventDateTime'] < $b['eventDateTime']) ? 1 : -1;
  });
}

function getProspectionViewData() {
  $showFull=(Parameter::getGlobalParameter('ImputOfAmountClient')!='HT');
  $data=array(
    'amountMode' => $showFull ? 'TTC' : 'HT',
    'yearN'      => intval(date('Y')),
    'rows'       => array(),
    'thumbs'     => array(),
  );

  $labels=prospectionViewLabels();
  $thumbs=array();

  // 1. active prospects, most recently worked first. NULL sorts last on DESC,
  //    so prospects with no action fall to the bottom, as intended.
  $prospects=array();
  $q=Sql::query("SELECT id, prospectNameCompany, prospectNameContact, email, idDomainProspect,"
              . " idProspectionSource, idProspectQualification, idLanguage,"
              . " idEngagement, idStatus, idResource, toBeRecontacted, lastEventDatetime"
              . " FROM prospect WHERE idle=0"
              . " ORDER BY lastEventDatetime DESC, id DESC");
  $order=array();
  while ($r=Sql::fetchLine($q)) { $prospects[$r['id']]=$r; $order[]=$r['id']; }
  $prospectIn=prospectionViewInClause($order);

  // 1bis. clients that hang from no prospect. They get a line of their own : the
  //       screen would otherwise never show them.
  $clientsSeuls=array();
  $q=Sql::query("SELECT id FROM client c WHERE c.idle=0"
              . " AND NOT EXISTS (SELECT 1 FROM link l WHERE"
              . "   (l.ref1Type='Client' AND l.ref1Id=c.id AND l.ref2Type='Prospect')"
              . "   OR (l.ref2Type='Client' AND l.ref2Id=c.id AND l.ref1Type='Prospect'))");
  while ($r=Sql::fetchLine($q)) { $clientsSeuls[intval($r['id'])]=intval($r['id']); }
  if (! count($prospects) and ! count($clientsSeuls)) return $data;

  // 2. links, read in both directions : nothing in the schema fixes which end
  //    holds the prospect.
  $clientsOf=array();
  $contactsOf=array();
  $q=Sql::query("SELECT ref1Type, ref1Id, ref2Type, ref2Id FROM link"
              . " WHERE (ref1Type='Prospect' AND ref1Id IN $prospectIn)"
              . "    OR (ref2Type='Prospect' AND ref2Id IN $prospectIn)");
  while ($r=Sql::fetchLine($q)) {
    if ($r['ref1Type']=='Prospect') { $pid=$r['ref1Id']; $oType=$r['ref2Type']; $oId=$r['ref2Id']; }
    else                            { $pid=$r['ref2Id']; $oType=$r['ref1Type']; $oId=$r['ref1Id']; }
    if (! isset($prospects[$pid])) continue;
    if ($oType=='Client')  $clientsOf[$pid][intval($oId)]=intval($oId);
    if ($oType=='Contact') $contactsOf[$pid][intval($oId)]=intval($oId);
  }

  $allClients=array();
  foreach ($clientsOf as $lst) { foreach ($lst as $id) { $allClients[$id]=$id; } }
  // The lone clients join the pack : sections 3 to 9 then serve them unchanged.
  foreach ($clientsSeuls as $id) { $allClients[$id]=$id; }

  // 3. the linked clients
  $clients=array();
  if (count($allClients)) {
    $q=Sql::query("SELECT id, name, idDomainProspect, idProspectQualification,"
                . " idLanguage, idStatus, idResource"
                . " FROM client WHERE id IN " . prospectionViewInClause($allClients)
                . " ORDER BY name");
    while ($r=Sql::fetchLine($q)) { $clients[$r['id']]=$r; }
  }

  // 4. contacts : those of the linked clients, plus those linked to a prospect
  $allLinkedContacts=array();
  foreach ($contactsOf as $lst) { foreach ($lst as $id) { $allLinkedContacts[$id]=$id; } }
  $contacts=array();
  $contactsByClient=array();
  if (count($allClients) or count($allLinkedContacts)) {
    $q=Sql::query("SELECT id, name, fullName, email, idClient, idProspectQualification, idLanguage"
                . " FROM resource WHERE isContact=1"
                . " AND (idClient IN " . prospectionViewInClause($allClients)
                . " OR id IN " . prospectionViewInClause($allLinkedContacts) . ")"
                . " ORDER BY name");
    while ($r=Sql::fetchLine($q)) {
      $contacts[$r['id']]=$r;
      if ($r['idClient']) $contactsByClient[$r['idClient']][intval($r['id'])]=intval($r['id']);
    }
  }

  // 5. prospection actions : prospects, clients and contacts mixed, most recent
  //    first. An action written on a contact fiche hangs from the contact, and
  //    is reached by no other route : it needs its own condition.
  $eventsOfProspect=array();
  $eventsOfClient=array();
  $eventsOfContact=array();
  $clientCond=count($allClients)
            ? " OR (refType='Client' AND refId IN " . prospectionViewInClause($allClients) . ")"
            : "";
  $contactCond=count($contacts)
            ? " OR (refType='Contact' AND refId IN " . prospectionViewInClause(array_keys($contacts)) . ")"
            : "";
  $q=Sql::query("SELECT refType, refId, id, eventDateTime, name, idProspectEventType, idContact"
              . " FROM prospectevent"
              . " WHERE (refType='Prospect' AND refId IN $prospectIn)"
              . $clientCond
              . $contactCond
              . " ORDER BY eventDateTime DESC, id DESC");
  while ($r=Sql::fetchLine($q)) {
    if      ($r['refType']=='Prospect') $eventsOfProspect[$r['refId']][]=$r;
    else if ($r['refType']=='Contact')  $eventsOfContact[$r['refId']][]=$r;
    else                                $eventsOfClient[$r['refId']][]=$r;
  }

  // 6. prospect estimates, hanging from the prospect itself. It has neither
  //    sendDate nor receptionDate : creationDate is the only comparable field.
  $estimatesOf=array();
  $q=Sql::query("SELECT id, idProject, idProspect, name, creationDate, idStatus,"
              . " untaxedAmount, untaxedAmountLocal, fullAmount, fullAmountLocal"
              . " FROM prospectestimate WHERE idProspect IN $prospectIn"
              . " ORDER BY creationDate DESC, id DESC");
  while ($r=Sql::fetchLine($q)) { $estimatesOf[$r['idProspect']][]=$r; }

  // 7 to 9. quotations, commands and bills hang from the clients.
  $quotationsOf=array();
  $commandsOf=array();
  $billsOf=array();
  if (count($allClients)) {
    $clientIn=prospectionViewInClause($allClients);

    $q=Sql::query("SELECT id, idProject, idClient, name, sendDate, idStatus,"
                . " untaxedAmount, untaxedAmountLocal, fullAmount, fullAmountLocal"
                . " FROM quotation WHERE idClient IN $clientIn"
                . " ORDER BY sendDate DESC, id DESC");
    while ($r=Sql::fetchLine($q)) { $quotationsOf[$r['idClient']][]=$r; }

    $q=Sql::query("SELECT id, idProject, idClient, name, receptionDate, idStatus,"
                . " untaxedAmount, untaxedAmountLocal, fullAmount, fullAmountLocal"
                . " FROM command WHERE idClient IN $clientIn"
                . " ORDER BY receptionDate DESC, id DESC");
    while ($r=Sql::fetchLine($q)) { $commandsOf[$r['idClient']][]=$r; }

    // Every bill but the cancelled ones, those sent to the bin kept. Whether a bill
    // is settled only decides its share of the turnover, not whether it is listed.
    $q=Sql::query("SELECT id, idProject, idClient, name, date, idStatus, paymentDone,"
                . " untaxedAmount, untaxedAmountLocal, fullAmount, fullAmountLocal"
                . " FROM bill WHERE idClient IN $clientIn"
                . " AND cancelled=0"
                . " ORDER BY date DESC, id DESC");
    while ($r=Sql::fetchLine($q)) { $billsOf[$r['idClient']][]=$r; }
  }

  // ---- the lines, both populations merged and sorted by freshness ----------
  // A prospect is dated by lastEventDatetime, a lone client by the most recent
  // action of its own or of its contacts. A line with no date closes the march,
  // as a prospect with no action already did.
  $lignes=array();
  foreach ($order as $pid) {
    $lignes[]=array('genre'=>'prospect', 'id'=>$pid, 'date'=>$prospects[$pid]['lastEventDatetime']);
  }
  foreach ($clientsSeuls as $cid) {
    $date=null;
    if (isset($eventsOfClient[$cid])) {
      foreach ($eventsOfClient[$cid] as $e) { if ($date===null or $e['eventDateTime']>$date) $date=$e['eventDateTime']; }
    }
    if (isset($contactsByClient[$cid])) {
      foreach ($contactsByClient[$cid] as $coid) {
        if (! isset($eventsOfContact[$coid])) continue;
        foreach ($eventsOfContact[$coid] as $e) { if ($date===null or $e['eventDateTime']>$date) $date=$e['eventDateTime']; }
      }
    }
    $lignes[]=array('genre'=>'client', 'id'=>$cid, 'date'=>$date);
  }
  usort($lignes, function($a, $b) {
    if ($a['date']===$b['date']) return 0;
    if ($a['date']===null) return 1;
    if ($b['date']===null) return -1;
    return ($a['date'] < $b['date']) ? 1 : -1;
  });

  // ---- assembly, no query below this line ---------------------------------
  foreach ($lignes as $ligne) {
    // A client that hangs from no prospect opens its own line : the Informations
    // block starts on the client itself, and no prospect line precedes it.
    if ($ligne['genre']=='client') {
      $cid=$ligne['id'];
      if (! isset($clients[$cid])) continue;
      $c=$clients[$cid];
      $statutNom  =isset($labels['Status'][$c['idStatus']]) ? $labels['Status'][$c['idStatus']]['name'] : '';
      $statutColor=isset($labels['Status'][$c['idStatus']]) ? $labels['Status'][$c['idStatus']]['color'] : '';
      $row=array(
        'id'              => intval($cid),
        'kind'            => 'client',
        'sortDate'        => $ligne['date'],
        'name'            => (string)$c['name'],
        'qualification'   => prospectionViewName($labels, 'ProspectQualification', $c['idProspectQualification']),
        // A client carries neither : the two columns stay empty, and the two filters
        // that read them will not retain this line.
        'engagement'      => '',
        'source'          => '',
        'status'          => $statutNom,
        'responsible'     => prospectionViewName($labels, 'Affectable', $c['idResource']),
        'idDomain'        => intval($c['idDomainProspect']),
        'idSource'        => 0,
        'idQualification' => intval($c['idProspectQualification']),
        'idEngagement'    => 0,
        'idStatus'        => intval($c['idStatus']),
        'idResponsible'   => intval($c['idResource']),
        'info'            => array(),
        'events'          => array(),
      );

      $row['info'][]=prospectionViewInfoLine('Client', $cid, 'client', array(
        'company'       => $c['name'],
        'domain'        => prospectionViewName($labels, 'DomainProspect', $c['idDomainProspect']),
        'qualification' => prospectionViewName($labels, 'ProspectQualification', $c['idProspectQualification']),
        'language'      => prospectionViewName($labels, 'Language', $c['idLanguage']),
        'status'        => $statutNom,
        'statusColor'   => $statutColor,
        'responsible'   => prospectionViewName($labels, 'Affectable', $c['idResource']),
        'idResponsible' => prospectionViewThumb($labels, $c['idResource'], $thumbs),
      ));

      $mesContacts=isset($contactsByClient[$cid]) ? $contactsByClient[$cid] : array();
      foreach ($mesContacts as $coid) {
        if (! isset($contacts[$coid])) continue;
        $co=$contacts[$coid];
        $row['info'][]=prospectionViewInfoLine('Contact', $coid, 'contact', array(
          'company'       => prospectionViewName($labels, 'Client', $co['idClient']),
          'contact'       => $co['fullName'] ? $co['fullName'] : $co['name'],
          'email'         => $co['email'],
          'qualification' => prospectionViewName($labels, 'ProspectQualification', $co['idProspectQualification']),
          'language'      => prospectionViewName($labels, 'Language', $co['idLanguage']),
        ));
      }

      // Actions : its own and its contacts'.
      $events=array();
      if (isset($eventsOfClient[$cid])) { foreach ($eventsOfClient[$cid] as $e) { $events[]=$e; } }
      foreach ($mesContacts as $coid) {
        if (! isset($eventsOfContact[$coid])) continue;
        foreach ($eventsOfContact[$coid] as $e) { $events[]=$e; }
      }
      prospectionViewSortEvents($events);
      // A client has no date to be called back : the column stays empty.
      foreach ($events as $e) { $row['events'][]=prospectionViewEventLine($labels, $e, ''); }

      $noms=array($row['name']);
      foreach ($row['info'] as $l) {
        if ($l['company']!=='') $noms[]=$l['company'];
        if ($l['contact']!=='') $noms[]=$l['contact'];
      }
      $row['search']=pq_strtolower(implode(' ', array_unique($noms)));

      // Prospect estimates hang from a prospect : an empty block, which draws no
      // total row, rather than a missing key the screen would have to guard.
      $row['estimates'] =prospectionViewMoneyBlock($labels, 'ProspectEstimate', array(), 'creationDate', $showFull);
      $row['quotations']=prospectionViewMoneyBlock($labels, 'Quotation',
        isset($quotationsOf[$cid]) ? $quotationsOf[$cid] : array(), 'sendDate', $showFull);
      $row['commands']  =prospectionViewMoneyBlock($labels, 'Command',
        isset($commandsOf[$cid]) ? $commandsOf[$cid] : array(), 'receptionDate', $showFull);
      $row['bills']     =prospectionViewBillBlock($labels,
        isset($billsOf[$cid]) ? $billsOf[$cid] : array(), $showFull, $data['yearN']);

      $data['rows'][]=$row;
      continue;
    }

    $pid=$ligne['id'];
    $p=$prospects[$pid];
    $myClients=isset($clientsOf[$pid]) ? $clientsOf[$pid] : array();

    $status=prospectionViewName($labels, 'Status', $p['idStatus']);
    // The header filters compare identifiers, the labels stay for the free text
    // search and for anything that reads the row without the lists at hand.
    $row=array(
      'id'              => intval($pid),
      'kind'            => 'prospect',
      'sortDate'        => $ligne['date'],
      'name'            => (string)$p['prospectNameCompany'],
      'qualification'   => prospectionViewName($labels, 'ProspectQualification', $p['idProspectQualification']),
      'engagement'      => prospectionViewName($labels, 'Engagement', $p['idEngagement']),
      'source'          => prospectionViewName($labels, 'ProspectionSource', $p['idProspectionSource']),
      'status'          => isset($labels['Status'][$p['idStatus']]) ? $labels['Status'][$p['idStatus']]['name'] : '',
      'responsible'     => prospectionViewName($labels, 'Affectable', $p['idResource']),
      'idDomain'        => intval($p['idDomainProspect']),
      'idSource'        => intval($p['idProspectionSource']),
      'idQualification' => intval($p['idProspectQualification']),
      'idEngagement'    => intval($p['idEngagement']),
      'idStatus'        => intval($p['idStatus']),
      'idResponsible'   => intval($p['idResource']),
      'info'            => array(),
      'events'          => array(),
    );

    // Informations : clients first, then the prospect, then the contacts.
    foreach ($myClients as $cid) {
      if (! isset($clients[$cid])) continue;
      $c=$clients[$cid];
      $row['info'][]=prospectionViewInfoLine('Client', $cid, 'client', array(
        'company'       => $c['name'],
        'domain'        => prospectionViewName($labels, 'DomainProspect', $c['idDomainProspect']),
        'qualification' => prospectionViewName($labels, 'ProspectQualification', $c['idProspectQualification']),
        'language'      => prospectionViewName($labels, 'Language', $c['idLanguage']),
        'status'        => isset($labels['Status'][$c['idStatus']]) ? $labels['Status'][$c['idStatus']]['name'] : '',
        'statusColor'   => isset($labels['Status'][$c['idStatus']]) ? $labels['Status'][$c['idStatus']]['color'] : '',
        'responsible'   => prospectionViewName($labels, 'Affectable', $c['idResource']),
        'idResponsible' => prospectionViewThumb($labels, $c['idResource'], $thumbs),
      ));
    }

    $row['info'][]=prospectionViewInfoLine('Prospect', $pid, 'prospect', array(
      'company'       => $p['prospectNameCompany'],
      'contact'       => $p['prospectNameContact'],
      'domain'        => prospectionViewName($labels, 'DomainProspect', $p['idDomainProspect']),
      'source'        => prospectionViewName($labels, 'ProspectionSource', $p['idProspectionSource']),
      'email'         => $p['email'],
      'qualification' => $row['qualification'],
      'language'      => prospectionViewName($labels, 'Language', $p['idLanguage']),
      'engagement'    => $row['engagement'],
      'engagementColor' => isset($labels['EngagementColor'][$p['idEngagement']]) ? $labels['EngagementColor'][$p['idEngagement']] : '',
      'status'        => $row['status'],
      'statusColor'   => isset($labels['Status'][$p['idStatus']]) ? $labels['Status'][$p['idStatus']]['color'] : '',
      'responsible'   => $row['responsible'],
      'idResponsible' => prospectionViewThumb($labels, $p['idResource'], $thumbs),
    ));

    // A contact reachable both through its client and through a link appears once.
    $myContacts=isset($contactsOf[$pid]) ? $contactsOf[$pid] : array();
    foreach ($myClients as $cid) {
      if (! isset($contactsByClient[$cid])) continue;
      foreach ($contactsByClient[$cid] as $coid) { $myContacts[$coid]=$coid; }
    }
    foreach ($myContacts as $coid) {
      if (! isset($contacts[$coid])) continue;
      $co=$contacts[$coid];
      // The contact carries both names, as a prospect does : its own in the contact
      // column, its client's in the company one, so the line reads on its own.
      // fullName holds the name, name being often empty on a contact.
      $row['info'][]=prospectionViewInfoLine('Contact', $coid, 'contact', array(
        'company'       => prospectionViewName($labels, 'Client', $co['idClient']),
        'contact'       => $co['fullName'] ? $co['fullName'] : $co['name'],
        'email'         => $co['email'],
        'qualification' => prospectionViewName($labels, 'ProspectQualification', $co['idProspectQualification']),
        'language'      => prospectionViewName($labels, 'Language', $co['idLanguage']),
      ));
    }

    // Actions : the prospect's, its clients' and its contacts', merged then
    // sorted again. Each source is already sorted, but merging sorted lists is
    // not sorted. myContacts is deduplicated, so no action is taken twice.
    $events=array();
    if (isset($eventsOfProspect[$pid])) { foreach ($eventsOfProspect[$pid] as $e) { $events[]=$e; } }
    foreach ($myClients as $cid) {
      if (! isset($eventsOfClient[$cid])) continue;
      foreach ($eventsOfClient[$cid] as $e) { $events[]=$e; }
    }
    foreach ($myContacts as $coid) {
      if (! isset($eventsOfContact[$coid])) continue;
      foreach ($eventsOfContact[$coid] as $e) { $events[]=$e; }
    }
    prospectionViewSortEvents($events);
    $toBeRecontacted=htmlFormatDate($p['toBeRecontacted'], true);
    foreach ($events as $e) { $row['events'][]=prospectionViewEventLine($labels, $e, $toBeRecontacted); }

    // The name filter searches every name of the line, prospect, clients and
    // contacts. Folded to lower case once here, not on every keystroke.
    $noms=array($row['name']);
    foreach ($row['info'] as $ligne) {
      if ($ligne['company']!=='') $noms[]=$ligne['company'];
      if ($ligne['contact']!=='') $noms[]=$ligne['contact'];
    }
    // The prospect name appears twice, as the row name and as its own line.
    $row['search']=pq_strtolower(implode(' ', array_unique($noms)));

    // Financial : one sub block per object. Totals are summed on the raw amount
    // and formatted once, because adding already formatted strings breaks as soon
    // as a project carries its own currency.
    $estimates=isset($estimatesOf[$pid]) ? $estimatesOf[$pid] : array();
    $row['estimates']=prospectionViewMoneyBlock($labels, 'ProspectEstimate', $estimates, 'creationDate', $showFull);

    $quotations=array(); $commands=array(); $bills=array();
    foreach ($myClients as $cid) {
      if (isset($quotationsOf[$cid])) { foreach ($quotationsOf[$cid] as $r) { $quotations[]=$r; } }
      if (isset($commandsOf[$cid]))   { foreach ($commandsOf[$cid] as $r)   { $commands[]=$r; } }
      if (isset($billsOf[$cid]))      { foreach ($billsOf[$cid] as $r)      { $bills[]=$r; } }
    }
    $row['quotations']=prospectionViewMoneyBlock($labels, 'Quotation', $quotations, 'sendDate', $showFull);
    $row['commands']  =prospectionViewMoneyBlock($labels, 'Command', $commands, 'receptionDate', $showFull);
    $row['bills']     =prospectionViewBillBlock($labels, $bills, $showFull, $data['yearN']);

    $data['rows'][]=$row;
  }

  $data['thumbs']=$thumbs;
  return $data;
}

/**
 * Assembles a financial sub block and its fixed footer total.
 */
function prospectionViewMoneyBlock($labels, $refType, $records, $dateField, $showFull) {
  $lines=array();
  $total=0;
  foreach ($records as $r) {
    $lines[]=prospectionViewMoneyLine($labels, $refType, $r, $dateField, $showFull);
    $total+=floatval($showFull ? $r['fullAmount'] : $r['untaxedAmount']);
  }
  return array(
    'lines' => $lines,
    'total' => count($lines) ? htmlDisplayCurrency($total) : '',
  );
}

/**
 * The bills sub block carries three amount columns instead of one : the turnover,
 * and its share on the current and the previous year, split on the bill date.
 * Only a settled bill feeds them : an unsettled one is listed with these cells empty.
 */
function prospectionViewBillBlock($labels, $records, $showFull, $yearN) {
  $lines=array();
  $total=0; $totalN=0; $totalN1=0;
  foreach ($records as $r) {
    $amount     =floatval($showFull ? $r['fullAmount']      : $r['untaxedAmount']);
    $amountLocal=$showFull ? $r['fullAmountLocal'] : $r['untaxedAmountLocal'];
    $raw        =$showFull ? $r['fullAmount']      : $r['untaxedAmount'];
    $formatted  =htmlDisplayLocalCurrency($r['idProject'], $raw, $amountLocal);
    $year       =intval(pq_substr((string)$r['date'], 0, 4));
    $settled    =(intval($r['paymentDone'])==1);
    $lines[]=array(
      'refType'     => 'Bill',
      'refId'       => intval($r['id']),
      'name'        => (string)$r['name'],
      'date'        => htmlFormatDate($r['date'], true),
      'ca'          => $settled ? $formatted : '',
      'caN'         => ($settled and $year==$yearN)   ? $formatted : '',
      'caNMinus1'   => ($settled and $year==$yearN-1) ? $formatted : '',
      'status'      => isset($labels['Status'][$r['idStatus']]) ? $labels['Status'][$r['idStatus']]['name'] : '',
      'statusColor' => isset($labels['Status'][$r['idStatus']]) ? $labels['Status'][$r['idStatus']]['color'] : '',
    );
    if ($settled) {
      $total+=$amount;
      if ($year==$yearN)   $totalN+=$amount;
      if ($year==$yearN-1) $totalN1+=$amount;
    }
  }
  return array(
    'lines'          => $lines,
    'totalCA'        => count($lines) ? htmlDisplayCurrency($total)   : '',
    'totalCAN'       => count($lines) ? htmlDisplayCurrency($totalN)  : '',
    'totalCANMinus1' => count($lines) ? htmlDisplayCurrency($totalN1) : '',
  );
}
