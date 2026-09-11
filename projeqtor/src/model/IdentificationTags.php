<?php
require_once('_securityCheck.php');

class IdentificationTags {
  
  private static $_aliasMap = null;
  private static $_aliasesByLength = array();
  private static $_maxAliasLength = 0;
  
  public static function transformRawHtml($value) {
    if ($value === null || $value === '') return $value;
    if (pq_strpos($value, '@') === false) return $value;
    
    return self::transformValue($value);
  }
  
  public static function transformObjectMentions($obj) {
    if (!is_object($obj)) return;
    
    foreach ($obj as $field => $value) {
      if (pq_substr($field, 0, 1) == '_') continue;
      if (is_object($value) || is_array($value)) continue;
      if ($value === null || $value === '') continue;
      if (pq_strpos($value, '@') === false) continue;

      if (!self::isMentionableField($obj, $field)) continue;

      $newValue = self::transformValue($value);
      if ($newValue !== $value) {
        $obj->$field = $newValue;
      }
    }
  }

  private static function isMentionableField($obj, $field) {
    $dataType = $obj->getDataType($field);
    if (in_array($dataType, array('mediumtext', 'text', 'longtext'))) return true;
    if ($dataType == 'varchar') {
      return ((int)$obj->getDataLength($field) >= 4000);
    }
    return false;
  }

  public static function extractObjectMentionTargets($obj) {
    $targets = array();
    if (!is_object($obj)) return $targets;

    foreach ($obj as $field => $value) {
      if (pq_substr($field, 0, 1) == '_') continue;
      if (is_object($value) || is_array($value)) continue;
      if ($value === null || $value === '') continue;
      if (!self::isMentionableField($obj, $field)) continue;

      $fieldTargets = self::extractMentionTargets($value);
      foreach ($fieldTargets as $key => $target) {
        $targets[$key] = $target;
      }
    }

    return $targets;
  }
  
  private static function transformValue($value) {
    self::prepareAliasMap();
    
    if (!count(self::$_aliasMap)) return $value;
    
    return isTextFieldHtmlFormatted($value)
    ? self::transformHtml($value)
    : self::transformPlainText($value);
  }
  
  private static function replaceMentions($text, &$changed) {
    if ($text === null || $text === '' || pq_strpos($text, '@') === false) return $text;
    
    $result = '';
    $offset = 0;
    
    while (($atPos = pq_strpos($text, '@', $offset)) !== false) {
      $match = self::findMentionInText($text, $atPos);
      
      if (!$match) {
        $result .= pq_substr($text, $offset, $atPos - $offset + 1);
        $offset = $atPos + 1;
        continue;
      }
      
      $result .= pq_substr($text, $offset, $match['start'] - $offset);
      $result .= $match['prefix'] . self::buildLinkHtml($match['mentionText'], $match['target']);
      $offset = $match['end'];
      $changed = true;
    }
    
    if (!$changed) return $text;
    
    $result .= pq_substr($text, $offset);
    return $result;
  }
  
  private static function transformPlainText($value) {
    $changed = false;
    $result = self::replaceMentions($value, $changed);
    
    if (!$changed) return $value;
    
    return nl2br($result);
  }
  
  private static function transformHtml($html) {
    $dom = new DOMDocument();
    libxml_use_internal_errors(true);
    
    $wrappedHtml = '<div id="pqMentionRoot">'.$html.'</div>';
    $loaded = $dom->loadHTML('<?xml encoding="utf-8" ?>'.$wrappedHtml, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);
    
    libxml_clear_errors();
    
    if (!$loaded) return $html;
    
    $xpath = new DOMXPath($dom);
    $textNodes = $xpath->query("//text()[not(ancestor::a) and not(ancestor::span[contains(concat(' ', normalize-space(@class), ' '), ' pqMentionLink ')])]");
    
    $changed = false;
    
    foreach ($textNodes as $textNode) {
      $text = $textNode->nodeValue;
      if (pq_strpos($text, '@') === false) continue;
      
      $newText = self::replaceMentions($text, $changed);
      
      if ($newText !== $text) {
        $fragment = $dom->createDocumentFragment();
        @$fragment->appendXML($newText);
        if ($fragment) {
          $textNode->parentNode->replaceChild($fragment, $textNode);
        }
      }
    }
    
    if (!$changed) return $html;
    
    $root = $dom->getElementById('pqMentionRoot');
    if (!$root) return $html;
    
    return self::getInnerHtml($root);
  }
  
  private static function getInnerHtml($node) {
    $html = '';
    foreach ($node->childNodes as $child) {
      $html .= $node->ownerDocument->saveHTML($child);
    }
    return $html;
  }
  
  private static function buildLinkHtml($mentionText, $target) {
    $name = (!empty($target['label'])) ? $target['label'] : $mentionText;
    return '<span class="pqMentionLink" contenteditable="false"'
        .' data-mention-class="'.htmlEncode($target['objectClass']).'"'
        .' data-mention-id="'.htmlEncode($target['id']).'"'
        .' data-mention-name="'.htmlEncode($name).'">@'.htmlEncode($mentionText).'</span>';
  }
  
  private static function findTarget($mentionText) {
    self::prepareAliasMap();
    
    $key = self::normalizeAlias($mentionText);
    if (!pq_array_key_exists($key, self::$_aliasMap)) return null;
    
    return self::$_aliasMap[$key];
  }

  public static function resolveAlias($alias) {
    return self::findTarget($alias);
  }

  private static function findMentionInText($text, $atPos) {
    if (!count(self::$_aliasMap)) return null;
    
    $prefix = '';
    $start = $atPos;
    
    if ($atPos > 0) {
      $prefix = pq_substr($text, $atPos - 1, 1);
      if (!preg_match('/[\s\(>]/', $prefix)) return null;
      $start = $atPos - 1;
    }
    
    $textLength = pq_strlen($text);
    $candidateStart = $atPos + 1;
    if ($candidateStart >= $textLength) return null;
    
    $candidateLength = self::$_maxAliasLength + 1;
    $remainingLength = $textLength - $candidateStart;
    if ($candidateLength > $remainingLength) {
      $candidateLength = $remainingLength;
    }
    $candidate = pq_substr($text, $candidateStart, $candidateLength);
    
    foreach (self::$_aliasesByLength as $alias) {
      $aliasLength = pq_strlen($alias);
      $candidatePart = pq_substr($candidate, 0, $aliasLength);
      $normalizedCandidate = self::normalizeAlias($candidatePart);
      if ($normalizedCandidate !== $alias) continue;
      
      $nextChar = pq_substr($text, $candidateStart + $aliasLength, 1);
      if ($nextChar !== '' && !preg_match('/[\s<\),;\.\!\?]/', $nextChar)) continue;
      
      return array(
          'start' => $start,
          'end' => $candidateStart + $aliasLength,
          'prefix' => $prefix,
          'mentionText' => pq_substr($text, $candidateStart, $aliasLength),
          'target' => self::$_aliasMap[$alias]
      );
    }
    
    return null;
  }

  private static function extractTextMentionTargets($value) {
    $targets = array();
    
    if (!count(self::$_aliasMap) || pq_strpos($value, '@') === false) return $targets;
    
    $text = strip_tags($value);
    $offset = 0;
    
    while (($atPos = pq_strpos($text, '@', $offset)) !== false) {
      $match = self::findMentionInText($text, $atPos);
      
      if (!$match) {
        $offset = $atPos + 1;
        continue;
      }
      
      $target = $match['target'];
      $targetKey = $target['objectClass'].'#'.$target['id'];
      $targets[$targetKey] = $target;
      $offset = $match['end'];
    }
    
    return $targets;
  }

  public static function getMentionableList() {
    $result = array();
    $aff = new Affectable();
    $list = $aff->getSqlElementsFromCriteria(array('idle' => '0'));
    $doFollowup = (Parameter::getUserParameter('mentionDetectionFollowup') == 'YES');
    $doMail = (Parameter::getUserParameter('mentionDetectionMail') == 'YES');
    $doNotification = (Parameter::getUserParameter('mentionDetectionNotification') == 'YES');

    foreach ($list as $item) {
      if (!$item->id) continue;

      $objectClass = self::detectObjectClass($item);
      $fullName = isset($item->name) ? $item->name : '';
      $userName = isset($item->userName) ? $item->userName : '';
      $profileName = (!empty($item->idProfile)) ? SqlList::getNameFromId('Profile', $item->idProfile) : '';
      $photoUrl = Affectable::getThumbUrl($objectClass, $item->id, 32, true, true);
      $hasEmail = (!empty($item->email));
      $isResource = (!empty($item->isResource) && $item->isResource == 1 && empty($item->isResourceTeam) && empty($item->isMaterial));
      $isResourceTeam = (!empty($item->isResourceTeam) && $item->isResourceTeam == 1);
      $canMentionFollowup = true;
      $canMentionMail = $hasEmail;
      $canMentionNotification = ($objectClass == 'User');
      if ($isResourceTeam) {
        $canMentionFollowup = false;
        $canMentionMail = false;
        $canMentionNotification = false;
        $members = self::getPoolMemberMentionTargets($item->id);
        foreach ($members as $member) {
          $canMentionFollowup = true;
          if (!$canMentionMail && self::getMentionMailAddress($member['id'])) {
            $canMentionMail = true;
          }
          if (!$canMentionNotification && self::canReceiveMentionNotification($member['id'])) {
            $canMentionNotification = true;
          }
          if ($canMentionMail && $canMentionNotification) break;
        }
      }
      $initials = self::getDbInitials($item, $objectClass);
      if (!$initials) {
        $initials = self::buildInitials($fullName);
      }

      $insert = '';
      if ($userName) {
        $insert = $userName;
      } else if ($fullName) {
        $insert = $fullName;
      } else if ($initials) {
        $insert = $initials;
      }

      $result[] = array(
          'id' => $item->id,
          'objectClass' => $objectClass,
          'initials' => $initials,
          'fullName' => $fullName,
          'userName' => $userName,
          'profileName' => $profileName,
          'photoUrl' => $photoUrl,
          'hasEmail' => $hasEmail,
          'isResource' => $isResource,
          'isResourceTeam' => $isResourceTeam,
          'canMentionFollowup' => $canMentionFollowup,
          'canMentionMail' => $canMentionMail,
          'canMentionNotification' => $canMentionNotification,
          'mentionFollowupActive' => $doFollowup,
          'mentionMailActive' => $doMail,
          'mentionNotificationActive' => $doNotification,
          'insert' => $insert
      );
    }

    usort($result, function($a, $b) {
      return strcasecmp($a['fullName'].' '.$a['userName'], $b['fullName'].' '.$b['userName']);
    });

    return $result;
  }
  
  private static function prepareAliasMap() {
    if (self::$_aliasMap !== null) return;
    
    self::$_aliasMap = array();
    
    $rawRealNameAliases = array();
    $rawUserNameAliases = array();
    $rawDbInitialAliases = array();
    $rawComputedInitialAliases = array();
    
    $aff = new Affectable();
    $list = $aff->getSqlElementsFromCriteria(array('idle' => '0'));
    
    foreach ($list as $item) {
      if (!$item->id) continue;
      
      $objectClass = self::detectObjectClass($item);
      
      $name = isset($item->name) ? $item->name : null;
      $userName = isset($item->userName) ? $item->userName : null;

      $label = (!empty($name)) ? $name : ((!empty($userName)) ? $userName : ('#'.$item->id));

      $target = array(
          'id' => $item->id,
          'objectClass' => $objectClass,
          'label' => $label
      );
      $dbInitials = self::getDbInitials($item, $objectClass);
      $computedInitials = self::buildInitials($name);
      
      self::registerAlias($rawRealNameAliases, $name, $target);
      self::registerAlias($rawUserNameAliases, $userName, $target);
      self::registerAlias($rawDbInitialAliases, $dbInitials, $target);
      self::registerAlias($rawComputedInitialAliases, $computedInitials, $target);
    }
    
    $finalAliases = array();
    
    self::mergeAliasGroup($finalAliases, $rawRealNameAliases, 'realName');
    self::mergeAliasGroup($finalAliases, $rawUserNameAliases, 'userName');
    self::mergeAliasGroup($finalAliases, $rawDbInitialAliases, 'dbInitials');
    self::mergeAliasGroup($finalAliases, $rawComputedInitialAliases, 'computedInitials');
    
    self::$_aliasMap = $finalAliases;
    
    if (!count(self::$_aliasMap)) {
      self::$_aliasesByLength = array();
      self::$_maxAliasLength = 0;
      return;
    }
    
    $aliasList = array_keys(self::$_aliasMap);
    usort($aliasList, function($a, $b) {
      return pq_strlen($b) - pq_strlen($a);
    });
    
    self::$_aliasesByLength = $aliasList;
    self::$_maxAliasLength = 0;
    foreach ($aliasList as $alias) {
      $aliasLength = pq_strlen($alias);
      if ($aliasLength > self::$_maxAliasLength) {
        self::$_maxAliasLength = $aliasLength;
      }
    }
  }
  
  private static function registerAlias(&$rawAliases, $alias, $target) {
    $alias = self::normalizeAlias($alias);
    if (!$alias) return;
    
    if (!pq_array_key_exists($alias, $rawAliases)) {
      $rawAliases[$alias] = array();
    }
    
    $rawAliases[$alias][] = $target;
  }
  
  private static function normalizeAlias($alias) {
    if ($alias === null || $alias === false) return null;
    
    $alias = (string)$alias;
    if ($alias === '') return null;
    
    $alias = strip_tags($alias);
    $alias = html_entity_decode($alias, ENT_QUOTES, 'UTF-8');
    $alias = pq_trim($alias);
    $alias = preg_replace('/\s+/u', ' ', $alias);
    $alias = pq_strtolower($alias);
    
    return ($alias === '') ? null : $alias;
  }
  
  private static function buildInitials($fullName) {
    if ($fullName === null || $fullName === false) return '';
    
    $fullName = pq_trim(strip_tags((string)$fullName));
    if ($fullName === '') return '';
    
    $parts = preg_split('/[\s\-_.]+/u', $fullName);
    $initials = '';
    
    foreach ($parts as $part) {
      $part = pq_trim($part);
      if ($part === '') continue;
      $initials .= pq_substr($part, 0, 1);
    }
    
    return $initials;
  }
  
  private static function mergeAliasGroup(&$finalAliases, $rawAliases, $groupName) {
    foreach ($rawAliases as $alias => $targets) {
      if (pq_array_key_exists($alias, $finalAliases)) continue;
      if (count($targets) == 1) {
        $finalAliases[$alias] = reset($targets);
      }
    }
  }
  
  private static function detectObjectClass($item) {
    if (!empty($item->isResourceTeam) && $item->isResourceTeam == 1) return 'ResourceTeam';
    if (!empty($item->isUser) && $item->isUser == 1) return 'User';
    if (!empty($item->isResource) && $item->isResource == 1) return 'Resource';
    if (!empty($item->isContact) && $item->isContact == 1) return 'Contact';
    return 'Affectable';
  }
  
  private static function getDbInitials($item, $objectClass) {
    if (!$item || !$item->id) return null;
    
    $initials = null;
    
    if ($objectClass == 'User') {
      $obj = new User($item->id);
      if (!empty($obj->initials)) {
        $initials = $obj->initials;
      }
    } else if ($objectClass == 'Resource') {
      $obj = new Resource($item->id);
      if (!empty($obj->initials)) {
        $initials = $obj->initials;
      }
    } else if ($objectClass == 'ResourceTeam') {
      $obj = new ResourceTeam($item->id);
      if (!empty($obj->initials)) {
        $initials = $obj->initials;
      }
    } else if ($objectClass == 'Contact') {
      $obj = new Contact($item->id);
      if (!empty($obj->initials)) {
        $initials = $obj->initials;
      }
    }
    
    return $initials;
  }
  
  public static function extractMentionTargets($value) {
    $targets = array();
    
    if ($value === null || $value === '') return $targets;
    
    self::prepareAliasMap();
    
    if (pq_strpos($value, '@') !== false) {
      $targets = array_merge($targets, self::extractTextMentionTargets($value));
    }
    
    preg_match_all('/<span[^>]*class=["\'][^"\']*pqMentionLink[^"\']*["\'][^>]*>/i', $value, $spanMatches);

    foreach ($spanMatches[0] as $spanTag) {
      if (!preg_match('/data-mention-id=["\']([^"\']+)["\']/i', $spanTag, $idMatch)) continue;
      $objectClass = 'Affectable';
      if (preg_match('/data-mention-class=["\']([^"\']+)["\']/i', $spanTag, $classMatch)) {
        $objectClass = $classMatch[1];
      }
      $key = $objectClass.'#'.$idMatch[1];
      $targets[$key] = array(
          'objectClass' => $objectClass,
          'id' => $idMatch[1]
      );
    }

    preg_match_all("/gotoElement\\('([^']+)'\\s*,\\s*'([^']+)'\\)/", $value, $linkMatches, PREG_SET_ORDER);
    
    foreach ($linkMatches as $match) {
      $key = $match[1].'#'.$match[2];
      $targets[$key] = array(
          'objectClass' => $match[1],
          'id' => $match[2]
      );
    }
    
    return $targets;
  }

  private static function expandMentionTargetsForActions($mentions) {
    $targets = array();

    foreach ($mentions as $mention) {
      if (self::isPoolMentionTarget($mention)) {
        $poolTargets = self::getPoolMemberMentionTargets($mention['id']);
        foreach ($poolTargets as $key => $target) {
          $targets[$key] = $target;
        }
      } else {
        $target = self::normalizeMentionTarget($mention);
        if (!$target) continue;
        $targets[$target['objectClass'].'#'.$target['id']] = $target;
      }
    }

    return $targets;
  }

  private static function normalizeMentionTarget($mention) {
    if (!isset($mention['id']) || !$mention['id']) return null;

    $id = $mention['id'];
    $affectable = new Affectable($id);
    if (!$affectable->id || $affectable->idle) return null;

    $target = array(
        'id' => $affectable->id,
        'objectClass' => self::detectObjectClass($affectable)
    );
    if (isset($mention['label'])) {
      $target['label'] = $mention['label'];
    }

    return $target;
  }

  private static function isPoolMentionTarget($mention) {
    if (!isset($mention['id']) || !$mention['id']) return false;
    if (isset($mention['objectClass']) && $mention['objectClass'] == 'ResourceTeam') return true;

    $affectable = new Affectable($mention['id']);
    return ($affectable->id && !$affectable->idle && !empty($affectable->isResourceTeam) && $affectable->isResourceTeam == 1);
  }

  private static function getPoolMemberMentionTargets($idPool) {
    $targets = array();
    $poolMember = new ResourceTeamAffectation();
    $poolMemberList = $poolMember->getSqlElementsFromCriteria(array(
        'idResourceTeam' => $idPool,
        'idle' => '0'
    ));

    foreach ($poolMemberList as $poolMember) {
      if (!$poolMember->idResource) continue;

      $member = new Affectable($poolMember->idResource);
      if (!$member->id || $member->idle) continue;
      if (!empty($member->isMaterial) && $member->isMaterial == 1) continue;

      $objectClass = self::detectObjectClass($member);
      $target = array(
          'id' => $member->id,
          'objectClass' => $objectClass,
          'label' => isset($member->name) ? $member->name : null,
          '_fromPool' => $idPool
      );
      $targets[$objectClass.'#'.$member->id] = $target;
    }

    return $targets;
  }

  private static function canReceiveMentionNotification($idAffectable) {
    $user = new User($idAffectable);
    return ($user->id && !$user->idle);
  }

  private static function getMentionMailAddress($idAffectable) {
    $user = new User($idAffectable);
    if ($user->id && !$user->idle && !empty($user->email)) return $user->email;

    $affectable = new Affectable($idAffectable);
    if ($affectable->id && !$affectable->idle && !empty($affectable->email)) return $affectable->email;

    return null;
  }
  
  public static function processMentionActions($mentions, $note, $refType, $refId) {
    if (!count($mentions)) return;
    
    $doFollowup = (Parameter::getUserParameter('mentionDetectionFollowup') == 'YES');
    $doMail = (Parameter::getUserParameter('mentionDetectionMail') == 'YES');
    $doNotification = (Parameter::getUserParameter('mentionDetectionNotification') == 'YES');
    
    if (!$doFollowup && !$doMail && !$doNotification) return;
    
    $sender = getSessionUser();
    $targetObject = new $refType($refId);
    $title = i18n($refType).' #'.$refId;
    $noteContent = (is_object($note) && property_exists($note, 'note')) ? $note->note : '';
    $notifiable = SqlElement::getSingleSqlElementFromCriteria('Notifiable', array(
        'notifiableItem' => $refType
    ));
    $mentions = self::expandMentionTargetsForActions($mentions);
    
    foreach ($mentions as $mention) {
      $idAffectable = $mention['id'];
      
      if ($doFollowup) {
        $sub = SqlElement::getSingleSqlElementFromCriteria('Subscription', array(
            'idAffectable' => $idAffectable,
            'refType' => $refType,
            'refId' => $refId
        ));
        
        if (!$sub->id) {
          $sub->idAffectable = $idAffectable;
          $sub->refType = $refType;
          $sub->refId = $refId;
          $sub->idUser = $sender->id;
          $sub->creationDateTime = date('Y-m-d H:i:s');
          $sub->comment = i18n('tagsInNoteFollowupComment');
          $sub->isAutoSub = 1;
          $sub->save();
        }
      }
      
      if ($doNotification && self::canReceiveMentionNotification($idAffectable)) {
        $notif = new Notification();
        $notif->idUser = $idAffectable;
        $notif->idResource = $sender->id;
        $notif->creationDateTime = date('Y-m-d H:i:s');
        $notif->name = i18n('tagsInNote');
        $notif->title = i18n('getTagsInNote');
        $notificationItemTitle = $title;
        if ($notifiable->id) {
          $notif->idNotifiable = $notifiable->id;
          $notif->notifiedObjectId = $refId;
        } else {
          $notificationItemTitle = '<span'
              .' onClick="gotoElement(\''.htmlEncode($refType).'\',\''.htmlEncode($refId).'\')"'
              .' style="color:var(--color-secondary);cursor:pointer;text-decoration:underline;">'
              .$title
              .'</span>';
        }
        $notif->content = $sender->name.' '.i18n('getTagsInNoteBy').' '.$notificationItemTitle;
        if ($noteContent) {
          $notif->content .= '<br/><br/>'.$noteContent;
        }
        $notif->notificationDate = date('Y-m-d');
        $newtimestamp = pq_strtotime('Now + 1 minute');
        $notif->notificationTime = date('H:i:s', $newtimestamp);
        $notif->idNotificationType = SqlList::getIdFromName('NotificationType', 'INFO');
        $notif->idStatusNotification = 1;
        $notif->sendEmail = 0;
        $notif->_fromMention = true;
        $notif->save();
      }
      
      if ($doMail) {
        $mailAddress = self::getMentionMailAddress($idAffectable);
        if ($mailAddress) {
          $url = $targetObject->getReferenceUrl();
          $message = ($sender->resourceName??$sender->name).' '.i18n('getTagsInNoteBy').' ';
          $message .= '<a href="'.htmlEncode($url).'">'.$title.'</a>';
          if ($noteContent) {
            $message .= '<br/><br/>'.$noteContent;
          }
          $dbName=Parameter::getGlobalParameter('paramDbDisplayName');
          $mailTitle=(($dbName)?'['.$dbName.'] ':'').i18n('tagsInNoteMail');
          sendMail(
              $mailAddress,
              $mailTitle,
              $message
              );
        }
      }
    }
  }
}
