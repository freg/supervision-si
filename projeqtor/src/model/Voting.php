<?php


class Voting extends SqlElement
{
    public $id;    // redefine $id to specify its visible place
    public $idUser;
    public $idClient;
    public $idVoter;
    public $refType;
    public $refId;
    public $value;
    public $idNote;
    
    public function __construct($id = NULL, $withoutDependentObjects=false)
    {
      parent::__construct($id,$withoutDependentObjects);
      if ($withoutDependentObjects) return;
    }
    
    public function __destruct() {
      parent::__destruct();
    }
    
    public function save() {
      if ($this->refType=='TicketSimple') $this->refType='Ticket';
      $result = parent::save();
      return $result;
    }
}