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

/* ============================================================================
 * RiskType defines the type of a risk.
 */  
require_once('_securityCheck.php');
class InputMailboxHistory extends SqlElement {
  
  public $_sec_Description;
  public $id;
  public $refType;
  public $idInputMailbox;
  public $adress;
  public $title;
  public $date; 
  public $result; 
  public $_noHistory=true;
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

  public static function storeHistory($mb,$subject,$from,$result,$rejection=true, $refType=null) {
    // Trace history
    if ($rejection) {
      debugTraceLog("[IMB".(($refType=="import")?'I':'T')."#$mb->id] ImapMailbox($mb->serverImap,$mb->imapUserAccount,$mb->pwdImap)");
      errorLog("Error on ".(($refType=="import")?'Import':'Ticket')." mailbox #$mb->id | $mb->serverImap | $mb->imapUserAccount");
      errorLog($result);
      errorLog("Last IMAP Error :".imap_last_error());
    }
    if (!$mb->id) return;
    
    // Store History
    $inputMailboxHistory = new InputMailboxHistory();
    $inputMailboxHistory->idInputMailbox = $mb->id;
    $inputMailboxHistory->title = pq_mb_substr($subject,0,200);
    $inputMailboxHistory->adress = $from;
    $inputMailboxHistory->date = date("Y-m-d H:i:s");
    if($refType=="import"){
      $inputMailboxHistory->result=pq_mb_substr( (($rejection)?i18n('importRejected').' : ':"").$result,0,200);
    }else{
      $inputMailboxHistory->result=pq_mb_substr( (($rejection)?i18n('ticketRejected').' : ':"").$result,0,200);
    }
    $inputMailboxHistory->refType = $refType;
    $inputMailboxHistory->save();
  }
}
?>