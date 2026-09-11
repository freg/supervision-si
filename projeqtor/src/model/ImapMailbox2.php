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

/**
 *
 * @see 
 * @author 
 *        
 */
require_once ('_securityCheck.php');
require_once ('../external/PHPImap/autoload.php');
use Webklex\PHPIMAP\ClientManager;
use Webklex\PHPIMAP\Client;
use Webklex\PHPIMAP\Config;
//require_once ('..\external\PHPImap\Traits\HasEvents.php');
//require_once ('..\external\PHPImap\ClientManager.php');
require_once ('../external/PHPImap/webklex/php-imap/src/Config.php');
//require_once ('..\external\PHPImap\Client.php');
//require_once ('..\external\PHPImap\IMAP.php');
//require_once ('..\external\PHPImap\Support\Masks\Mask.php');
//require_once ('..\external\PHPImap\Support\Masks\MessageMask.php');
//require_once ('..\external\PHPImap\Support\Masks\AttachmentMask.php');

class ImapMailbox {

protected $client;
protected $attachmentsDir;
protected $folder;


  public function __construct($imapPath, $login, $password, $attachmentsDir=null, $serverEncoding='utf-8', $idOauthClient=null) {
    
    $encryption=false;
    $validate_cert=true;
    $end=pq_strpos($imapPath,'}');
    $serverStr=pq_substr($imapPath,1,$end-1);
    $exp=explode('/',$serverStr);
    $expSrv=explode(':',$exp[0]);
    $host=$expSrv[0];
    $port=$expSrv[1]??143;  // $port=(isset($expSrv[1]) and $expSrv[1])?$expSrv[1]:143;
    $this->folder=pq_substr($imapPath,$end+1);
    for ($i=1;$i<count($exp);$i++) {
      if ($exp[$i]=='novalidate-cert') $validate_cert=false;
      if ($exp[$i]=='ssl' or $exp[$i]=='tls') $encryption=$exp[$i];
    }
    
    include ('../external/PHPImap/webklex/php-imap/src/config/projeqtorImapConfig.php');
    $cfg=$projeqtorImapConfig;
    $cfg['accounts']['default']['host']=$host;
    $cfg['accounts']['default']['port']=$port;
    $cfg['accounts']['default']['encryption']=$encryption;
    $cfg['accounts']['default']['validate_cert']=$validate_cert;
    $cfg['accounts']['default']['username']=$login;
    $cfg['accounts']['default']['password']=$password;
    $cfg['accounts']['default']['protocol']='imap';
    if ($idOauthClient) {
      $oauth=new OAuthClient($idOauthClient);
      $cfg['accounts']['default']['authentication']='oauth';
      $cfg['accounts']['default']['password']=$oauth->getToken();
    }    
    $config=new Config($cfg);
    $this->client = new Client($config);

    //if ($idOauthClient) {$this->client->setToken($oauth->getToken());}

    if ($attachmentsDir) {
      if (!is_dir($attachmentsDir)) {
        throw new Exception('Directory "' . $attachmentsDir . '" not found');
      }
      $this->attachmentsDir = rtrim(realpath($attachmentsDir), '\\/');
    }
  }
  public function connect() {
    try {
      $this->client->connect();
    } catch (Exception $e) {
      throw new ImapMailboxException("connect() | ".$e->getMessage(),$this);
    }
  }
  
  public function disconnect() {
    $this->client->disconnect();
  }
  
  public function getImapStream($forceConnection=true) {
    static $imapStream;
    if ($forceConnection) {
      if ($imapStream&&(!is_resource($imapStream)||!imap_ping($imapStream))) {
        $this->disconnect();
        $imapStream=null;
      }
      if (!$imapStream) {
        $imapStream=$this->initImapStream();
      }
    }
    return $imapStream;
  }
  
    protected function initImapStream() {
        try {
            $this->client->connect();
        } catch (ConnectionFailedException $e) {
            throw new ImapMailboxException("initImapStream() | ".$e->getMessage(),$this);
        }
        return $this->client;
    }
  
  public function checkMailbox() {
    return $this->client->check();
  }
  
  public function searchMailbox($criteria='ALL') {
      if (! $this->folder or pq_trim($this->folder)=='') $this->folder='INBOX';
      try {
          $this->connect();
          $folder = $this->client->getFolder($this->folder);
          if (!$folder) {
            traceLog("searchMailbox() | cannot find folder $this->folder");
            return [];
          }
          $messages = $folder->query()->where(explode(" ",$criteria))->get();
          $id=0;
          $mailsIds = [];
          foreach ($messages as $message) {
              $mailsIds[] = $message->getUid();
              $id++;
          }
          return $mailsIds;
      } catch (ConnectionFailedException $e) {
          throw new ImapMailboxException("searchMailbox() | connection failed | ".$e->getMessage(),$this);
      } catch (RuntimeException $e) {
          throw new ImapMailboxException("searchMailbox() | runtime exception | ".$e->getMessage(),$this);
      }
  }
  
  public function deleteMail($mailId) {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $message = $folder->query()->getMessage($mailId);
    $message->delete();
    $this->disconnect();
  }
  
  public function expungeDeletedMails() {
    $this->connect();
    $this->client->expunge();
    $this->disconnect();
  }
  
  public function markMailAsRead($mailId) {
    if (!is_array($mailId)) {
      //$mailId=array($mailId);
    }
    $this->setFlag($mailId, 'Seen');
  }

  public function markMailAsUnread($mailId) {
    if (!is_array($mailId)) {
      //$mailId=array($mailId);
    }
    $this->clearFlag($mailId, 'Seen');
  }

  public function markMailAsImportant($mailId) {
    if (!is_array($mailId)) {
      //$mailId=array($mailId);
    }
    $this->setFlag($mailId, 'Flagged');
  }
  
  /*
   * Causes a store to add the specified flag to the flags set for the mails in the specified sequence.
   *
   * @param array $mailsIds
   * @param $flag Flags which you can set are \Seen, \Answered, \Flagged, \Deleted, and \Draft as defined by RFC2060.
   * @return bool
   */
    protected function setFlag($mailId, $flag) {
      $this->connect();
      $folder = $this->client->getFolder($this->folder);
      $message = $folder->query()->getMessage($mailId);
      $message->setFlag($flag);
      $this->disconnect();
    }

  /*
   * Cause a store to delete the specified flag to the flags set for the mails in the specified sequence.
   *
   * @param array $mailsIds
   * @param $flag Flags which you can set are \Seen, \Answered, \Flagged, \Deleted, and \Draft as defined by RFC2060.
   * @return bool
   */
  protected function clearFlag($mailId, $flag) {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $message = $folder->query()->getMessage($mailId);
    $message->unsetFlag($flag);
    $this->disconnect();
  }
  
 
  public function getMailsInfo(array $mailsIds) {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $messages = $folder->query()->whereUid($mailsIds)->get();
    $this->disconnect();
    return $messages;
  }
  
  public function sortMails($criteria = 'arrival', $reverse = true) {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $query = $folder->query()->sortBy($criteria, $reverse);
    $messages = $query->get();
    $this->disconnect();
    return $messages->pluck('uid')->toArray();
  }
  
  public function countMails() {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $count = $folder->messages()->count();
    $this->disconnect();
    return $count;
  }
  
  public function getMail($mailId) {
    $this->connect();
    $folder = $this->client->getFolder($this->folder);
    $message = $folder->query()->getMessage($mailId);
    $mail=new IncomingMailboxItem();
    $mail->id=$mailId;
    $mail->date=$message->getAttributes()["date"]->toString();
    $mail->subject=$message->getAttributes()["subject"]->toString();
//     $from=explode(" ",$message->getAttributes()["from"]->toString());
//     if(!isset($from[2])){
//       $mail->fromName=$from[0];
//     }else{
//       $mail->fromName=$from[0]." ".$from[1];
//     }
//     if(!isset($from[2])){
//       $mail->fromAddress=pq_substr($from[1], 1, -1);
//     }else{
//       $mail->fromAddress=pq_substr($from[2], 1, -1);
//     }
    $arrayFrom=array('from','sender','fromaddress','senderaddress');
    foreach($arrayFrom as $fromTest) {
      if (! isset($message->getAttributes()[$fromTest])) continue;
      if (! $message->getAttributes()[$fromTest]) continue;
      $test=$message->getAttributes()[$fromTest];
      $posTag=strrpos($test, '<');
      $posSpace=strrpos($test, ' ');
      if ($posTag!==false) {
        $mail->fromAddress=pq_str_replace(array('<','>'),'',pq_substr($test,$posTag));
        $mail->fromName=pq_substr($test,0,$posTag-1);
        if (pq_strpos($mail->fromAddress,'@')!==false) break;
      }else if ($posSpace!==false) {
        $mail->fromAddress=pq_str_replace(array('<','>'),'',pq_substr($test,$posSpace));
        $mail->fromName=pq_substr($test,0,$posSpace-1);
        if (pq_strpos($mail->fromAddress,'@')!==false) break;
      }
    }
    $mail->to=$message->getAttributes()["to"]->toArray();
    $mail->toString=$message->getAttributes()["to"]->toString();
    $mail->cc=$message->getCc()->toArray();
    $mail->replyTo=($message->getAttributes()["reply_to"]??'')->toString();
    $mail->textHtml=$message->getHTMLBody();
    $mail->textPlain=$message->getTextBody();
    $ctpAtt=0;
    foreach ($message->getAttachments() as $attach){
      $ctpAtt++;
      $attachAttr=$attach->getAttributes();
      $attachmentId=$attachAttr['id'];
      $fileName=$attachAttr['filename'];
      $fileStorageName=preg_replace('~[\\\\/]~', '', $mail->id.'_'.$attachmentId.'_'.$fileName);
      $filesStoragePath=$this->attachmentsDir;
      $targetPath=$filesStoragePath.DIRECTORY_SEPARATOR.$fileStorageName; 
      $attach ->save($filesStoragePath,$fileStorageName);
      $attObj=new IncomingMailboxItemAttachment();
      $attObj->id=$attachmentId;
      $attObj->name=$fileName;
      $attObj->filePath=$targetPath;
      $mail->addAttachment($attObj);
    }
    
    
    $this->disconnect();
    return $mail;
  }
  
  public static function checkImapEnabled() {
    if (function_exists('imap_search')) {
      return true;
    } else {
      return false;
    }
  }
  
 protected function initMailPart(IncomingMailboxItem $mail, $partStructure, $partNum) {
   $data=$partNum?imap_fetchbody($this->getImapStream(), $mail->id, $partNum, FT_UID):imap_body($this->getImapStream(), $mail->id, FT_UID);
 
   if ($partStructure->encoding==1) {
     $data=imap_utf8($data);
   } elseif ($partStructure->encoding==2) {
     $data=imap_binary($data);
   } elseif ($partStructure->encoding==3) {
     $data=imap_base64($data);
   } elseif ($partStructure->encoding==4) {
     $data=imap_qprint($data);
   }
 
   $params=array();
   if (!empty($partStructure->parameters)) {
     foreach ($partStructure->parameters as $param) {
       $params[pq_strtolower($param->attribute)]=$param->value;
     }
   }
   if (!empty($partStructure->dparameters)) {
     foreach ($partStructure->dparameters as $param) {
       $params[pq_strtolower($param->attribute)]=$param->value;
     }
   }
   if (!empty($params['charset'])) {
     if (! $this->serverEncoding or ! pq_trim($this->serverEncoding)) $this->serverEncoding='utf-8';
     if ($this->serverEncoding!='utf-8') traceLog("ImapMailbox conversion from '".$params['charset']."' to '".$this->serverEncoding."'");
     $dataSav=$data;
     enableSilentErrors();
     $data=iconv($params['charset'], $this->serverEncoding, $data);
     if (pq_strlen($data)==0 and pq_strlen($dataSav)>0) {
       $data=$dataSav; // if no conversion possible, keep format as is
     }
     disableSilentErrors();
   }
   // attachments
   $attachmentId=$partStructure->ifid?pq_trim($partStructure->id, " <>"):(isset($params['filename'])||isset($params['name'])?mt_rand().mt_rand():null);
   if ($attachmentId) {
     if (empty($params['filename'])&&empty($params['name'])) {
       $fileName=$attachmentId.'.'.pq_strtolower($partStructure->subtype);
     } else {
       $fileName=!empty($params['filename'])?$params['filename']:$params['name'];
       $fileName=$this->decodeMimeStr($fileName);
       $replace=array('/\s/'=>'_', '/[^0-9a-zA-Z_\.]/'=>'', '/_+/'=>'_', '/(^_)|(_$)/'=>'');
       $fileName=preg_replace(array_keys($replace), pq_nvl($replace), pq_nvl($fileName));
     }
     $attachment=new IncomingMailboxItemAttachment();
     $attachment->id=$attachmentId;
     $attachment->name=$fileName;
     if ($this->attachmentsDir) {
       $attachment->filePath=$this->attachmentsDir.DIRECTORY_SEPARATOR.preg_replace('~[\\\\/]~', '', $mail->id.'_'.$attachmentId.'_'.$fileName);
       file_put_contents($attachment->filePath, $data);
     }
     $mail->addAttachment($attachment);
   } elseif ($partStructure->type==0&&$data) {
     if (pq_strtolower($partStructure->subtype)=='plain') {
       $mail->textPlain.=$data;
     } else {
       $mail->textHtml.=$data;
     }
   } elseif ($partStructure->type==2&&$data) {
     $mail->textPlain.=pq_trim($data);
   }
   if (!empty($partStructure->parts)) {
     foreach ($partStructure->parts as $subPartNum=>$subPartStructure) {
       $this->initMailPart($mail, $subPartStructure, $partNum.'.'.($subPartNum+1));
     }
   }
 }
 
 protected function decodeMimeStr($string, $charset='UTF-8') {
   $newString='';
   $elements=imap_mime_header_decode($string);
   for ($i=0; $i<count($elements); $i++) {
     if ($elements[$i]->charset=='default') {
       $elements[$i]->charset='iso-8859-1';
     }
     $newString.=iconv($elements[$i]->charset, $charset, $elements[$i]->text);
   }
   return $newString;
 }
 public function getClient() {
   return $this->client;
 }
}
 class IncomingMailboxItem {
 
   public $id;
   public $date;
   public $subject;
   public $fromName;
   public $fromAddress;
   public $to=array();
   public $toString;
   public $cc=array();
   public $replyTo=array();
   public $textPlain;
   public $textHtml;
 
   /**
    * @var IncomingMailboxItemAttachment[]
    */
   protected $attachments=array();
 
   public function addAttachment(IncomingMailboxItemAttachment $attachment) {
     $this->attachments[$attachment->id]=$attachment;
   }
 
   /**
    *
    * @return IncomingMailboxItemAttachment[]
    */
   public function getAttachments() {
     return $this->attachments;
   }
 
   /**
    * Get array of internal HTML links placeholders
    *
    * @return array attachmentId => link placeholder
    */
   public function getInternalLinksPlaceholders() {
     return preg_match_all('/=["\'](ci?d:(\w+))["\']/i', pq_nvl($this->textHtml), $matches)?array_combine($matches[2], $matches[1]):array();
   }
 
   public function replaceInternalLinks($baseUri) {
     $baseUri=pq_rtrim($baseUri, '\\/').'/';
     $fetchedHtml=$this->textHtml;
     foreach ($this->getInternalLinksPlaceholders() as $attachmentId=>$placeholder) {
       $fetchedHtml=pq_str_replace($placeholder, $baseUri.basename($this->attachments[$attachmentId]->filePath), $fetchedHtml);
     }
     return $fetchedHtml;
   }
 
 }
 
 class IncomingMailboxItemAttachment {
 
   public $id;
   public $name;
   public $filePath;
 
 }
 
  class ImapMailboxException extends Exception {
    function __construct($msg, $imapMailbox) {
      parent::__construct($msg);
      if (!$imapMailbox) $imapMailbox=new ImapMailbox();
      $client=$imapMailbox->getClient();
      $config=$client->getConfig()->getClientConfig(null); // 'host', 'port', 'encryption', 'validate_cert', 'username', 'password', 'protocol', 'authentication'
      $host=$config->get("host",'?');
      $user=$config->get("username",'?');
      $authentication=$config->get("authentication",'?');
      //ErrorLog("=> ImapMailboxException Host:$host User:$user Authentication:$authentication");
      ErrorLog("=> ImapMailboxException");
      ErrorLog("=> ".pq_str_replace(array("\r\n","\n"),array(" | "," "),$msg)); 
    }
  }